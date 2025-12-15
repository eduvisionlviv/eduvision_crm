"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

# Ми прибрали прямий імпорт httpx, бо більше не робимо ручних запитів
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
        # Імпортуємо httpx тільки тут, коли це справді треба
        import httpx 
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
    
    # Ми не передаємо жодних проксі. 
    # Нехай бібліотека використовує системні налаштування за замовчуванням.
    request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
    )

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
    LOGGER.info("🚀 Запуск Telegram бота (спрощений режим)...")
    
    # Ми прибрали блок try/catch з ручною перевіркою telegram_api_request.
    # Одразу запускаємо long polling. Бібліотека сама впорається з помилками з'єднання.
    try:
        app = get_application()
        app.run_polling(
            stop_signals=None,
            drop_pending_updates=True,
            allowed_updates=ALLOWED_UPDATES,
        )
    except Exception as e:
        LOGGER.error("❌ Telegram bot crashed: %s", e)
        # Не перезапускаємо в циклі тут, щоб не спамити логами, якщо все погано.
        # Gunicorn перезапустить worker, якщо треба.
