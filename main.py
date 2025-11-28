import os
import sys
import subprocess
import logging
import importlib.util
import pathlib
import asyncio
import time
import threading
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from playwright.async_api import async_playwright

from api import taskscheduler
from api.coreapiserver import with_global_lock
from api.load_module_apis import load_module_apis
from api.blueprint_utils import register_blueprints
from services import tg_bot

# ─────────────── Логування
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("main")

# ─────────────── Playwright: install chromium if missing ───────────
PLAYWRIGHT_CACHE = os.path.expanduser("~/.cache/ms-playwright")

def _install_playwright_chromium_if_needed():
    if not os.path.exists(PLAYWRIGHT_CACHE):
        try:
            log.info("⏳ Installing Playwright Chromium …")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                check=True
            )
            log.info("✅ Chromium installed for Playwright")
        except Exception as exc:
            log.error("❌ Playwright install failed: %s", exc)

# запуск інсталяції у фоні одразу при імпорті модуля
threading.Thread(target=_install_playwright_chromium_if_needed, daemon=True).start()

# ─────────────── Автозапуск і автостоп браузера ───────────
_browser = None
_pw = None
_browser_last_used = 0.0

# можна тюнити через env
_BROWSER_IDLE_TIMEOUT = int(os.getenv("PDF_BROWSER_IDLE", "60"))   # сек
_MONITOR_INTERVAL = int(os.getenv("PDF_MONITOR_INTERVAL", "30"))   # сек

async def _launch_browser():
    """Запускає Chromium, якщо він ще не запущений, і оновлює час останнього використання."""
    global _browser, _pw, _browser_last_used
    if _browser is None:
        if _pw is None:
            _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch(args=["--no-sandbox"])
        print("🚀 Chromium launched")
    _browser_last_used = time.time()
    return _browser

async def _close_browser_if_idle():
    """Закриває Chromium (і Playwright), якщо не використовувався довше таймаута."""
    global _browser, _pw
    if _browser is None:
        return
    idle = time.time() - _browser_last_used
    if idle >= _BROWSER_IDLE_TIMEOUT:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
        try:
            if _pw:
                await _pw.stop()
        except Exception:
            pass
        _pw = None
        print("💤 Chromium closed after idle timeout")

def _monitor_loop():
    """Фоновий монітор простою у окремому треді."""
    while True:
        try:
            asyncio.run(_close_browser_if_idle())
        except Exception:
            pass
        time.sleep(_MONITOR_INTERVAL)

def start_browser_monitor():
    threading.Thread(target=_monitor_loop, daemon=True).start()
    print("🛎️ Browser idle monitor started")

async def warmup_browser():
    """Попередній запуск браузера для швидкого першого PDF."""
    await _launch_browser()
    print("🔥 Browser warm-up complete")

# ─────────────── Flask App + CORS
app = Flask(__name__, static_folder="web", static_url_path="")
allowed = os.getenv("crm_url", "http://localhost:5000")
CORS(app, resources={r"/api/*": {"origins": [d.strip() for d in allowed.split(",")]}})

# ─────────────── Динамічне завантаження API-модулів
def load_api(app: Flask, folder: str = "api"):
    base = pathlib.Path(folder).resolve()
    for py in base.rglob("*.py"):
        if py.name.startswith("_"):
            continue
        mod_name = ".".join(("api",) + py.with_suffix("").parts)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)             # type: ignore
            blueprints = []
            bp = getattr(mod, "bp", None)
            if bp:
                blueprints.append(bp)
            extra_bps = getattr(mod, "bps", None)
            if extra_bps:
                if isinstance(extra_bps, (list, tuple, set)):
                    blueprints.extend(extra_bps)
                else:
                    blueprints.append(extra_bps)

            register_blueprints(app, blueprints, str(py.relative_to(base)), logger=log)
        except Exception as exc:
            log.error("⚠️  Skip %s : %s", py.relative_to(base), exc)

load_module_apis(app)
load_api(app)
with_global_lock(app)
taskscheduler.start_scheduler_once()
from services.test_mail_tool import bp as bp_test_mail
app.register_blueprint(bp_test_mail)

# ─────────────── Telegram бот (опціонально) ───────────
_telegram_thread = None
_telegram_token_missing_logged = False
_telegram_lock = threading.Lock()


def start_telegram_bot_if_configured():
    """Запускає Telegram-бота у фоні, якщо задано токен."""
    global _telegram_thread, _telegram_token_missing_logged

    with _telegram_lock:
        if _telegram_thread and _telegram_thread.is_alive():
            return

        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            if not _telegram_token_missing_logged:
                log.info("TELEGRAM_BOT_TOKEN не налаштовано — Telegram-бот не стартує.")
                _telegram_token_missing_logged = True
            return

        def _bot_worker():
            try:
                tg_bot.run_bot()
            except Exception as exc:  # pragma: no cover - лише для логування
                log.exception("Telegram-бот зупинився з помилкою: %s", exc)

        _telegram_thread = threading.Thread(
            target=_bot_worker,
            name="telegram-bot",
            daemon=True,
        )
        _telegram_thread.start()
        log.info("Telegram-бот запущено у фоні.")


def ensure_telegram_bot_started() -> None:
    """Прив'язує запуск бота до життєвого циклу Flask."""

    start_telegram_bot_if_configured()


app.before_request(ensure_telegram_bot_started)

# Імпорт у Gunicorn може відбуватися до першого HTTP-запиту, тому запускаємо бот одразу.
start_telegram_bot_if_configured()

# ─────────────── Routes
@app.route("/")
def root():
    return app.send_static_file("index.html")

@app.route("/img/<path:filename>")
def img_static(filename):
    return send_from_directory("img", filename)

@app.route("/module/<path:filepath>")
def module_static(filepath):
    return send_from_directory("module", filepath)

@app.route("/templates/<path:filename>")
def template_static(filename):
    return send_from_directory("templates", filename)

@app.route("/<path:path>")
def static_or_fallback(path: str):
    file_path = pathlib.Path(app.static_folder) / path
    if file_path.is_file():
        return send_from_directory(app.static_folder, path)
    return app.send_static_file("index.html")

@app.route("/ping")
def ping():
    return jsonify(status="ok")

# ─────────────── Локальний запуск
if __name__ == "__main__":
    # Стартуємо фоновий монітор
    start_browser_monitor()

    # Паралельно розпочинаємо Telegram-бота (якщо налаштовано токен)
    start_telegram_bot_if_configured()

    # Прогрів браузера у фоновому режимі (не блокує Flask)
    def _warmup_in_background():
        try:
            _install_playwright_chromium_if_needed()  # дочекаємось докачки Chromium
            asyncio.run(warmup_browser())
        except Exception as e:
            log.warning("Warm-up browser failed: %s", e)

    threading.Thread(target=_warmup_in_background, daemon=True).start()

    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# 💱 Перерахунок цін у sklad за курсом із uni_base(2).jsonb на старті
try:
    from api.coreapiserver import get_client_for_table
    from api.currency_update import _reprice_sklad_by_rate  # вже існує у твоєму проєкті

    base = get_client_for_table("uni_base")
    row = base.table("uni_base").select("jsonb").eq("id", 2).execute().data
    if not row:
        raise RuntimeError("uni_base(id=2) не знайдено")

    raw = row[0].get("jsonb")
    # jsonb може бути або числом, або об'єктом; пробуємо найтиповіші ключі
    if isinstance(raw, dict):
        rate = raw.get("usd_sale") or raw.get("usd") or raw.get("rate") or raw.get("sale")
    else:
        rate = raw
    rate = float(rate)

    _reprice_sklad_by_rate(rate)  # всередині оновлює price_uah = round(price_usd * rate, 2)
    print(f"💱 Repriced sklad on boot with rate={rate}")
except Exception as e:
    print(f"💱 Reprice on boot FAILED: {e}")
