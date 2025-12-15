"""Telegram-bot: Original Logic + Cloudflare Fix + Always Button."""
from __future__ import annotations

import logging
import os
import sys
import time
import socket
from typing import Optional

# --- 💉 DNS HARDFIX (Критично для Cloudflare Workers) ---
# Без цього фікса бот не зможе знайти адресу workers.dev
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

# --- НАЛАШТУВАННЯ ---
# Оновлений текст, щоб користувач розумів, навіщо кнопка
START_REPLY = "Вітаю! Я твій помічник від Helen Doron."
LINK_INSTRUCTION = (
    "📱 Щоб я міг тебе впізнати, мені потрібен твій номер телефону.\n"
    "Будь ласка, натисни кнопку нижче 👇"
)

BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"

CHOOSING, TYPING_REPLY = range(2)
# ✅ Додано список дозволених оновлень (щоб не було помилок)
ALLOWED_UPDATES = ["message", "contact", "callback_query"]

_application: Optional[Application] = None
_telebot: Optional[TeleBot] = None
_BOT_USERNAME: Optional[str] = os.getenv("BOT_USERNAME")

__all__ = ["run_bot", "get_application", "get_bot_token"]


# --- РОБОТА З ENV ---

def _load_env_from_file_once() -> None:
    pass # Вже не критично, змінні беруться з середовища

def get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        # Спроба читання з файлу (Docker Secrets)
        for file_path in [os.getenv("TELEGRAM_BOT_TOKEN_FILE"), os.getenv("BOT_TOKEN_FILE")]:
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f: return f.read().strip()
                except: pass
        LOGGER.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
        return "" 
    return token

def get_api_base() -> str:
    """Визначає правильну адресу API (Cloudflare Mirror)."""
    custom_base = os.getenv("TELEGRAM_API_BASE")
    if not custom_base:
        return "https://api.telegram.org/bot"
    
    # Автоматичне виправлення посилання (додаємо /bot якщо немає)
    base = custom_base.strip().rstrip("/")
    if not base.endswith("/bot"):
        base += "/bot"
    return base

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


# --- ХЕНДЛЕРИ ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє /start.
    МОДИФІКАЦІЯ: Кнопка показується ЗАВЖДИ, навіть без токена.
    """
    if not update.message: return

    # Перевірка deep linking (t.me/bot?start=TOKEN)
    args = context.args
    raw = args[0] if args else None
    token = raw.replace("-", ".") if raw else None

    if token:
        context.user_data["link_token"] = token
        LOGGER.info(f"🔑 Отримано токен: {token}")

    # Створюємо кнопку
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    # Відправляємо текст + кнопку
    await update.message.reply_text(f"{START_REPLY}\n\n{LINK_INSTRUCTION}", reply_markup=markup)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отримує контакт і відправляє на бекенд."""
    if not update.message or not update.message.contact: return

    token = context.user_data.get("link_token")
    
    contact = update.message.contact
    # Перевірка: чи це номер користувача?
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text("Це чужий номер. Надішліть свій.", reply_markup=ReplyKeyboardRemove())
        return

    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number,
    }

    try:
        # Збільшений тайм-аут для надійності
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(_link_callback_url(), json=payload)
            data = resp.json()
        
        bot_text = data.get("bot_text") or data.get("message") or "Дякую! Дані отримано."
        await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)
            
    except Exception as exc:
        LOGGER.error(f"Link recovery failed: {exc}")
        await update.message.reply_text("⚠️ Помилка з'єднання з сервером.", reply_markup=ReplyKeyboardRemove())


# --- ДІАЛОГИ ТА ЗАДАЧІ (З вашого оригінального коду) ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Діалог розпочато.")
    return TYPING_REPLY

async def conversation_store_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        context.user_data["last_reply"] = update.message.text
        await update.message.reply_text("Відповідь збережено.")
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

async def scheduled_heartbeat(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    # LOGGER.info("JobQueue heartbeat...")

def configure_jobqueue(job_queue: JobQueue) -> None:
    job_queue.run_repeating(scheduled_heartbeat, interval=3600, first=3600, data="heartbeat")

async def on_post_init(application: Application) -> None:
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅ БОТ @{me.username} ГОТОВИЙ")
    except Exception as e:
        LOGGER.warning(f"⚠️ Init warning: {e}")


# --- ЗАПУСК ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        api_base = get_api_base() # Використовуємо Cloudflare адресу
        
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
    LOGGER.info("🚀 Запуск (Original Logic + Fixes)...")
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
