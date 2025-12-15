"""Telegram-bot: Business Logic + Cloudflare Fix + Always Ask Contact."""
from __future__ import annotations

import logging
import os
import sys
import time
import socket
from pathlib import Path
from typing import Optional

# --- 💉 DNS HARDFIX (Лікуємо сліпоту сервера Hugging Face) ---
# Це критично для роботи через Cloudflare Workers
CF_IP = "104.21.80.1" 
_original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host and "workers.dev" in str(host):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (CF_IP, 443))]
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo
# ------------------------------------------------

import httpx
# Додаємо підтримку telebot для сумісності з вашим старим кодом
from telebot import TeleBot 

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    JobQueue,
    MessageHandler,
    filters,
)

# --- ЛОГУВАННЯ ---
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# --- КОНСТАНТИ ---
# Текст, який буде завжди при старті
START_REPLY = (
    "Вітаю! Я твій помічник від Helen Doron.\n\n"
    "Щоб я міг тебе впізнати та надати доступ до інформації, мені потрібен твій номер телефону.\n"
    "👇 Будь ласка, натисни кнопку нижче:"
)

BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"

CHOOSING, TYPING_REPLY = range(2)

# ✅ ОБОВ'ЯЗКОВА ЗМІННА
ALLOWED_UPDATES = ["message", "contact", "callback_query"]

_application: Optional[Application] = None
_telebot: Optional[TeleBot] = None
_BOT_USERNAME: Optional[str] = os.getenv("BOT_USERNAME")
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

__all__ = ["run_bot", "get_application", "get_bot_token"]


# --- РОБОТА З ENV ТА URL ---

def _load_env_from_file_once() -> None:
    global _ENV_LOADED
    if _ENV_LOADED: return
    env_path = os.getenv("ENV_FILE")
    env_file = Path(env_path) if env_path else _PROJECT_ROOT / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if not line or line.lstrip().startswith("#") or "=" not in line: continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except Exception: pass
    _ENV_LOADED = True

def get_bot_token() -> str:
    _load_env_from_file_once()
    for file_path in [os.getenv("TELEGRAM_BOT_TOKEN_FILE"), os.getenv("BOT_TOKEN_FILE")]:
        if file_path:
            try:
                if t := Path(file_path).read_text(encoding="utf-8").strip(): return t
            except FileNotFoundError: pass
    for key in ["TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN"]:
        if val := os.getenv(key): return val.strip()
    LOGGER.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
    return "" 

def get_api_base() -> str:
    """Визначає адресу API (Cloudflare Mirror)."""
    _load_env_from_file_once()
    custom_base = os.getenv("TELEGRAM_API_BASE")
    if not custom_base:
        return "https://api.telegram.org/bot"
    
    base = custom_base.strip().rstrip("/")
    if not base.endswith("/bot"):
        base += "/bot"
    return base

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


# --- ХЕНДЛЕРИ (Оновлена логіка кнопок) ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє /start.
    Тепер кнопка показується ЗАВЖДИ.
    """
    if not update.message: return

    # Перевіряємо, чи є токен у посиланні (deep linking)
    args = context.args
    raw = args[0] if args else None
    token = raw.replace("-", ".") if raw else None

    # Якщо токен є — запам'ятовуємо його, але кнопку показуємо все одно
    if token:
        context.user_data["link_token"] = token
        LOGGER.info(f"🔑 Отримано токен при старті: {token}")

    # --- СТВОРЕННЯ КНОПКИ ---
    # request_contact=True змушує Telegram надіслати картку контакту
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    # Відправляємо привітання З КНОПКОЮ
    await update.message.reply_text(START_REPLY, reply_markup=markup)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка отриманого контакту."""
    if not update.message or not update.message.contact: return

    user_token = context.user_data.get("link_token")
    contact = update.message.contact
    
    # Перевірка "свій/чужий" номер
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "⚠️ Це не ваш номер. Будь ласка, натисніть кнопку внизу, щоб надіслати ВЛАСНИЙ номер.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Готуємо дані для CRM
    payload = {
        "user_token": user_token,
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number,
        "first_name": contact.first_name,
        "last_name": contact.last_name
    }

    LOGGER.info(f"📤 Відправка контакту на сервер: {contact.phone_number}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_link_callback_url(), json=payload)
            data = resp.json()
        
        # Відповідь від сервера (має бути привітання з іменем)
        bot_text = data.get("bot_text") or data.get("message") or "Дякую! Ваш номер отримано."
        
        await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)
            
    except Exception as exc:
        LOGGER.error(f"❌ Помилка CRM: {exc}")
        await update.message.reply_text(
            "⚠️ Вибачте, не можу з'єднатися з базою даних. Спробуйте пізніше.", 
            reply_markup=ReplyKeyboardRemove()
        )


# --- ДІАЛОГИ ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Це демо-діалог. Напишіть щось.")
    return TYPING_REPLY

async def conversation_store_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        context.user_data["last_reply"] = update.message.text
        await update.message.reply_text("Збережено.")
    return ConversationHandler.END

async def conversation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Скасовано.")
    return ConversationHandler.END

def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("dialog", conversation_entry)],
        states={TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_store_reply)]},
        fallbacks=[CommandHandler("cancel", conversation_cancel)],
    )

def configure_jobqueue(job_queue: JobQueue) -> None:
    pass 

async def on_post_init(application: Application) -> None:
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅ БОТ @{me.username} АКТИВНИЙ")
    except Exception as e:
        LOGGER.warning(f"⚠️ Init Warning: {e}")

# --- SETUP ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        api_base = get_api_base()
        LOGGER.info(f"🌍 API Base: {api_base}")

        request = HTTPXRequest(
            connect_timeout=40.0,
            read_timeout=40.0,
            write_timeout=40.0,
            connection_pool_size=10,
        )

        application = (
            ApplicationBuilder()
            .token(token)
            .base_url(api_base)
            .request(request)
            .get_updates_request(request)
            .post_init(on_post_init)
            .build()
        )

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())
        configure_jobqueue(application.job_queue)

        _application = application
    return _application

def get_telebot() -> TeleBot:
    global _telebot
    if _telebot is None: _telebot = TeleBot(get_bot_token(), parse_mode="HTML")
    return _telebot

def run_bot() -> None:
    LOGGER.info("🚀 Запуск...")
    import urllib3
    urllib3.disable_warnings()

    while True:
        try:
            app = get_application()
            app.run_polling(
                stop_signals=[], 
                close_loop=False, 
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES
            )
            break
        except Exception as exc:
            LOGGER.error(f"❌ Crash: {exc}")
            global _application
            _application = None
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
