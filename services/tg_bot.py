"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import sys
import time  # <--- Додано для пауз
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


def _telegram_api_request(method: str, payload: dict, *, timeout: float = 15.0) -> dict:
    """Викликає Telegram Bot API через httpx і повертає декодовану відповідь."""

    token = get_bot_token()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Unknown Telegram error")
    return data


def send_message_httpx(chat_id: int, text: str) -> bool:
    """Надсилає повідомлення через Bot API без запуску поллінгу."""

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        _telegram_api_request("sendMessage", payload)
        return True
    except Exception as exc:
        LOGGER.error("Не вдалося надіслати повідомлення в Telegram: %s", exc)
        return False


def get_bot_username() -> str:
    """Повертає username бота або піднімає виняток із поясненням."""

    global _BOT_USERNAME
    if _BOT_USERNAME:
        return _BOT_USERNAME

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задано")

    try:
        data = _telegram_api_request("getMe", {})
        username = data.get("result", {}).get("username")
        if not username:
            raise RuntimeError("Bot API не повернув username")
        _BOT_USERNAME = username
        return username
    except Exception as exc:
        raise RuntimeError(f"Не вдалося отримати дані бота: {exc}") from exc


def get_bot_status() -> dict:
    """Повертає зрозумілий статус налаштування Telegram-бота."""

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    status: dict = {"configured": bool(token)}

    if not token:
        status["message"] = "TELEGRAM_BOT_TOKEN не задано. Додайте токен у змінні середовища."
        return status

    try:
        status["bot_username"] = get_bot_username()
        status["status"] = "ok"
    except Exception as exc:
        status["status"] = "error"
        status["message"] = str(exc)

    return status

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
    """Ця функція викликається ТІЛЬКИ коли є реальний зв'язок."""
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅✅✅ БОТ ПІДКЛЮЧИВСЯ! @{me.username} (ID: {me.id})")
    except Exception as e:
        LOGGER.warning(f"⚠️ post_init warning: {e}")

# --- APP BUILDER ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        
        # Максимально лояльні налаштування мережі
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
            .post_init(on_post_init)
            .build()
        )

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())

        _application = application
    return _application

def run_bot() -> None:
    """Головна функція запуску з вічним циклом перезавантаження."""
    application = get_application()
    
    LOGGER.info("🚀 Запуск Telegram бота... Входимо в режим очікування з'єднання...")

    while True:
        try:
            # Намагаємось запустити бота
            application.run_polling(
                stop_signals=None, 
                bootstrap_retries=-1, # Просимо лібу пробувати
                timeout=60
            )
            # Якщо run_polling завершився без помилок (наприклад, ми його зупинили), виходимо
            break
        except Exception as exc:
            # Якщо сталася помилка (наприклад, DNS), ловимо її тут
            LOGGER.error(f"❌ Збій з'єднання (DNS/Network): {exc}")
            LOGGER.info("🔄 Перезапуск бота через 10 секунд...")
            time.sleep(10)
            # І цикл починається знову -> application.run_polling()
