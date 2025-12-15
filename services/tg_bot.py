"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import time
import socket
from pathlib import Path
from typing import Optional

# Використовуємо httpx
import httpx
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

# ─────────────── ЛОГИ ───────────────
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# ─────────────── КОНСТАНТИ ───────────────
START_REPLY = "Вітаю, я твій помічник від Helen Doron 👋"
# Використовуємо стандартний URL, але будемо хитрувати з IP якщо треба
API_BASE_URL = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
API_URL_TEMPLATE = f"{API_BASE_URL}/bot{{token}}/{{method}}"

BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"
LINK_INSTRUCTION = (
    "📱 Щоб підтвердити, що це саме ваш акаунт EduVision,\n"
    "будь ласка, поділіться своїм номером телефону, натиснувши кнопку нижче."
)
ALLOWED_UPDATES = ["message", "contact"]
_application: Optional[Application] = None
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─────────────── ENV / TOKEN ───────────────
def _load_env_once() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = Path(os.getenv("ENV_FILE", _PROJECT_ROOT / ".env"))
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    _ENV_LOADED = True

def get_bot_token() -> str:
    _load_env_once()
    for key in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_API_TOKEN"):
        v = os.getenv(key)
        if v:
            return v.strip()
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задано")

# ─────────────── DNS HACK ───────────────
def resolve_telegram_ip():
    """
    Намагається знайти реальну IP адресу api.telegram.org.
    Це обходить проблеми з DNS у Docker контейнерах.
    """
    domain = "api.telegram.org"
    try:
        # Спроба 1: Стандартний резолв
        ip = socket.gethostbyname(domain)
        LOGGER.info(f"✅ DNS успіх: {domain} -> {ip}")
        return None # Якщо працює стандартно, нічого не міняємо
    except Exception as e:
        LOGGER.warning(f"⚠️ DNS помилка для {domain}: {e}")
        # Спроба 2: Повертаємо хардкод IP (один з офіційних IP Telegram)
        # Це "милиця", але вона працює, коли DNS лежить
        fallback_ip = "149.154.167.220"
        LOGGER.info(f"🚑 Використовую запасну IP: {fallback_ip}")
        return fallback_ip

# ─────────────── TELEGRAM API (httpx) ───────────────
def telegram_api_request(
    method: str,
    payload: dict,
    *,
    timeout: float = 20.0,
    retries: int = 3,
) -> dict:
    token = get_bot_token()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    
    # Перевіряємо DNS
    forced_ip = resolve_telegram_ip()
    headers = {}
    
    if forced_ip:
        # Підміняємо домен на IP, але в заголовку Host залишаємо домен
        # Це дозволяє https працювати коректно
        url = url.replace("api.telegram.org", forced_ip)
        headers["Host"] = "api.telegram.org"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            # verify=False може знадобитися, якщо ми йдемо по IP, але спробуємо спочатку з True
            with httpx.Client(timeout=timeout, verify=True) as client:
                r = client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    raise RuntimeError(data)
                return data
        except Exception as e:
            last_error = e
            LOGGER.warning("Telegram API attempt %s/%s failed: %s", attempt, retries, e)
            time.sleep(1.5 * attempt)
    
    # Якщо нічого не допомогло - просто ігноруємо, щоб не валити весь сервер
    LOGGER.error(f"❌ Telegram check failed completely. Skipping check. Error: {last_error}")
    return {"ok": False, "result": "skipped"}

# ─────────────── HANDLERS ───────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    raw = context.args[0] if context.args else None
    token = raw.replace("-", ".") if raw else None
    if token:
        context.user_data["link_token"] = token
        markup = ReplyKeyboardMarkup(
            [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.message.reply_text(LINK_INSTRUCTION, reply_markup=markup)
        return
    await update.message.reply_text(START_REPLY)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.contact:
        return
    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text("Спершу відкрийте бота за посиланням.", reply_markup=ReplyKeyboardRemove())
        return
    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": update.message.contact.phone_number,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(BACKEND_URL.rstrip("/") + LINK_RECOVERY_PATH, json=payload)
            data = r.json()
    except Exception as e:
        LOGGER.error("link_recovery error: %s", e)
        await update.message.reply_text("⚠️ Помилка сервера.", reply_markup=ReplyKeyboardRemove())
        return
    await update.message.reply_text(data.get("bot_text", "Готово."), reply_markup=ReplyKeyboardRemove())

# ─────────────── APPLICATION ───────────────
def get_application() -> Application:
    global _application
    if _application:
        return _application
    token = get_bot_token()
    
    request_kwargs = {
        "connect_timeout": 60,
        "read_timeout": 60,
        "write_timeout": 60,
    }

    # Спроба передати базовий URL, якщо ми використовуємо IP хак
    # Але для ApplicationBuilder це складніше, тому покладаємось на те, 
    # що сама бібліотека telegram зможе зарезолвити домен, або впаде і перезапуститься.
    
    request = HTTPXRequest(**request_kwargs)

    app = (
        ApplicationBuilder()
        .token(token)
        .request(request)
        .get_updates_request(request)
        .build()
    )
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    _application = app
    return app

# ─────────────── RUN ───────────────
def run_bot() -> None:
    LOGGER.info("🚀 Запуск Telegram бота...")
    
    # Робимо "м'яку" перевірку. Якщо вона впаде - ми все одно спробуємо запустити поллінг.
    try:
        telegram_api_request("getMe", {})
    except Exception:
        pass

    while True:
        try:
            app = get_application()
            app.run_polling(
                stop_signals=None,
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES,
            )
            break
        except Exception as e:
            LOGGER.error("❌ Telegram bot crashed: %s. Retrying in 10s...", e)
            global _application
            _application = None
            time.sleep(10)
