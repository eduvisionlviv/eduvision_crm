import os
import sys
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

# ─────────────── Playwright: керування браузером ───────────
# (КОД ІНСТАЛЯЦІЇ ВИДАЛЕНО, бо ми це зробили в Dockerfile)

_browser = None
_pw = None
_browser_last_used = 0.0

# Налаштування тайм-аутів
_BROWSER_IDLE_TIMEOUT = int(os.getenv("PDF_BROWSER_IDLE", "60"))   # сек
_MONITOR_INTERVAL = int(os.getenv("PDF_MONITOR_INTERVAL", "30"))   # сек

async def _launch_browser():
    """Запускає Chromium, якщо він ще не запущений."""
    global _browser, _pw, _browser_last_used
    if _browser is None:
        if _pw is None:
            _pw = await async_playwright().start()
        # Запускаємо без зайвих перевірок шляху, Playwright сам знайде його через ENV змінні
        _browser = await _pw.chromium.launch(args=["--no-sandbox"])
        print("🚀 Chromium launched")
    _browser_last_used = time.time()
    return _browser

async def _close_browser_if_idle():
    """Закриває Chromium, якщо він простоює."""
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
    """Фоновий монітор простою."""
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
    """Попередній запуск браузера."""
    try:
        await _launch_browser()
        print("🔥 Browser warm-up complete")
    except Exception as e:
        log.error(f"❌ Browser warm-up failed: {e}")

# ─────────────── Flask App + CORS
app = Flask(__name__, static_folder="web", static_url_path="")
allowed = os.getenv("crm_url", "http://localhost:5000")
CORS(app, resources={r"/api/*": {"origins": [d.strip() for d in allowed.split(",")]}})

# ─────────────── Динамічне завантаження API
def load_api(app: Flask, folder: str = "api"):
    base = pathlib.Path(folder).resolve()
    for py in base.rglob("*.py"):
        if py.name.startswith("_"):
            continue
        mod_name = ".".join(("api",) + py.with_suffix("").parts)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
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

# Спроба завантажити test_mail_tool (якщо файл існує)
try:
    from services.test_mail_tool import bp as bp_test_mail
    app.register_blueprint(bp_test_mail)
except ImportError:
    log.warning("⚠️ Module services.test_mail_tool not found, skipping.")

# ─────────────── Telegram бот ───────────
_telegram_thread = None
_telegram_lock = threading.Lock()

def start_telegram_bot_if_configured():
    global _telegram_thread
    with _telegram_lock:
        if _telegram_thread and _telegram_thread.is_alive():
            return

        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            if not _telegram_thread: # Логуємо тільки один раз
                 log.info("TELEGRAM_BOT_TOKEN не задано. Бот вимкнено.")
            return

        def _bot_worker():
            try:
                tg_bot.run_bot()
            except Exception as exc:
                log.exception("Telegram-бот впав: %s", exc)

        _telegram_thread = threading.Thread(
            target=_bot_worker, name="telegram-bot", daemon=True
        )
        _telegram_thread.start()
        log.info("Telegram-бот запущено у фоні.")

def ensure_telegram_bot_started() -> None:
    start_telegram_bot_if_configured()

app.before_request(ensure_telegram_bot_started)
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
    start_browser_monitor()
    start_telegram_bot_if_configured()

    # Прогрів браузера (без інсталяції, бо вже є)
    threading.Thread(target=lambda: asyncio.run(warmup_browser()), daemon=True).start()

    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ─────────────── Перерахунок цін (Опціонально) ───────────────
# Цей блок викликав помилку в логах. Додано безпечний імпорт.
try:
    from api.coreapiserver import get_client_for_table
    from api.currency_update import _reprice_sklad_by_rate
    
    base = get_client_for_table("uni_base")
    # Перевірка наявності таблиці/запису перед запитом
    try:
        row = base.table("uni_base").select("jsonb").eq("id", 2).execute().data
        if row:
            raw = row[0].get("jsonb")
            # Обробка різних форматів jsonb
            if isinstance(raw, dict):
                rate = float(raw.get("usd_sale") or raw.get("usd") or raw.get("rate") or raw.get("sale") or 0)
            else:
                rate = float(raw)
            
            if rate > 0:
                _reprice_sklad_by_rate(rate)
                print(f"💱 Ціни перераховано по курсу: {rate}")
    except Exception as e:
        print(f"💱 Помилка отримання курсу з БД: {e}")

except ImportError:
    print("💱 Модуль 'api.currency_update' не знайдено. Перерахунок цін пропущено.")
except Exception as e:
    print(f"💱 Reprice failed: {e}")
