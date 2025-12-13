"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import httpx
from telebot import TeleBot
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    JobQueue,
    MessageHandler,
    filters,
    ApplicationBuilder
)

LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

START_REPLY = "Вітаю я твій помічник від Helen Doron"
API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/{method}"
BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"
LINK_INSTRUCTION = (
    "📱 Щоб підтвердити, що це саме ваш акаунт EduVision,\n"
    "будь ласка, поділіться своїм номером телефону, натиснувши кнопку нижче."
)

CHOOSING, TYPING_REPLY = range(2)

_application: Optional[Application] = None
_telebot: Optional[TeleBot] = None
_BOT_USERNAME: Optional[str] = os.getenv("BOT_USERNAME")

__all__ = ["run_bot", "get_application"]

def get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")
    return token

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"

# --- HANDLERS ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.info(f"📩 Отримано /start від користувача {update.effective_user.id}")
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
    LOGGER.info(f"📩 Отримано контакт від {update.effective_user.id}")
    if not update.message or not update.message.contact:
        return

    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text("Спершу відкрийте бота за посиланням.", reply_markup=ReplyKeyboardRemove())
        return

    contact = update.message.contact
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text("Поділіться ВЛАСНИМ номером.", reply_markup=ReplyKeyboardRemove())
        return

    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id if update.effective_chat else None,
        "phone": contact.phone_number,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(_link_callback_url(), json=payload)
            data = response.json()
    except Exception as exc:
        LOGGER.error(f"Помилка link_recovery: {exc}")
        await update.message.reply_text("⚠️ Помилка сервера.", reply_markup=ReplyKeyboardRemove())
        return

    bot_text = data.get("bot_text") or data.get("message") or "Готово."
    await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

    if data.get("status") == "ok":
        context.user_data.pop("link_token", None)

# --- CONVERSATION ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Діалог розпочато. /cancel для виходу.")
    return TYPING_REPLY

async def conversation_store_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Відповідь збережено.")
    return ConversationHandler.END

async def conversation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Діалог скасовано.")
    return ConversationHandler.END

def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("dialog", conversation_entry)],
        states={TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_store_reply)]},
        fallbacks=[CommandHandler("cancel", conversation_cancel)],
    )

# --- STARTUP CHECK ---

async def on_post_init(application: Application) -> None:
    """Ця функція викликається, коли бот успішно з'єднався з Telegram."""
    me = await application.bot.get_me()
    LOGGER.info(f"✅✅✅ БОТ УСПІШНО ПІДКЛЮЧИВСЯ! Ім'я: @{me.username} (ID: {me.id})")
    LOGGER.info("Тепер ви можете писати йому /start")

# --- APP BUILDER ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        
        # Налаштування для стабільності мережі
        request_settings = HTTPXRequest(
            connect_timeout=60.0,
            read_timeout=60.0,
            write_timeout=60.0,
            connection_pool_size=8,
        )
        
        application = (
            ApplicationBuilder()
            .token(token)
            .request(request_settings)
            .get_updates_request(request_settings)
            .post_init(on_post_init) # <--- ДОДАНО ПЕРЕВІРКУ ПІДКЛЮЧЕННЯ
            .build()
        )

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())

        _application = application
    return _application

def run_bot() -> None:
    application = get_application()
    
    LOGGER.info("🚀 Запуск Telegram бота... Чекаємо на з'єднання...")

    # bootstrap_retries=-1 змушує бота довбати сервери Телеграм, поки не підключиться
    try:
        application.run_polling(stop_signals=None, bootstrap_retries=-1, timeout=60)
    except Exception as exc:
        LOGGER.error(f"❌ Критична помилка бота: {exc}")
