"""Telegram-бот: обробка контактів та стартових токенів.

Докладний покроковий опис — у docs/telegram_bot_flow.md.
"""
from __future__ import annotations

import logging
import os
import sys
import socket
import time
from typing import Optional

# --- 💉 DNS HARDFIX ---
CF_IP = "104.21.80.1" 
_original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host and "workers.dev" in str(host):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (CF_IP, 443))]
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo
# ----------------------

import httpx
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

# --- CONFIG ---
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

START_REPLY = (
    "Вітаю! Я твій помічник від Helen Doron. 👋\n\n"
    "Щоб я міг надати тобі доступ, мені потрібно звірити твій номер телефону.\n"
    "👇 Натисни кнопку нижче:"
)

BACKEND_URL = os.getenv("URL", "http://127.0.0.1:7860")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"

CHOOSING, TYPING_REPLY = range(2)
ALLOWED_UPDATES = ["message", "contact", "callback_query"]

_application: Optional[Application] = None
_telebot: Optional[TeleBot] = None
_BOT_USERNAME: Optional[str] = os.getenv("BOT_USERNAME")

__all__ = ["run_bot", "get_application", "get_bot_token"]


# --- HELPERS ---

def get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        for file_path in [os.getenv("TELEGRAM_BOT_TOKEN_FILE"), os.getenv("BOT_TOKEN_FILE")]:
            if file_path and os.path.exists(file_path):
                # ВИПРАВЛЕНО: Синтаксис з with open розгорнуто
                try:
                    with open(file_path, 'r') as f:
                        return f.read().strip()
                except Exception:
                    pass
        LOGGER.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return ""
    return token


def _get_crm_url() -> str:
    return (os.getenv("crm_url") or os.getenv("CRM_URL") or BACKEND_URL).rstrip("/")

def get_api_base() -> str:
    custom_base = os.getenv("TELEGRAM_API_BASE")
    if not custom_base: return "https://api.telegram.org/bot"
    base = custom_base.strip().rstrip("/")
    if not base.endswith("/bot"): base += "/bot"
    return base

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


# --- HANDLERS ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return

    args = context.args
    raw = args[0] if args else None
    token = raw.replace("-", ".") if raw else None

    if token:
        context.user_data["link_token"] = token
        LOGGER.info(f"🔑 Token found: {token}")

    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    await update.message.reply_text(START_REPLY, reply_markup=markup)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.contact: return

    token = context.user_data.get("link_token")
    contact = update.message.contact
    
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "⚠️ Це не ваш номер. Надішліть свій.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Payload Adjustment: No extra keys if token missing
    payload = {
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number
    }
    
    if token:
        payload["user_token"] = token

    LOGGER.info(f"📤 Sending to backend: {payload}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_link_callback_url(), json=payload)

        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code != 200:
            msg = data.get("bot_text") or "⚠️ Технічна помилка на сервері. Спробуйте пізніше."
            LOGGER.warning(f"CRM response {resp.status_code}: {resp.text}")
            await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
            return

        bot_text = data.get("bot_text") or data.get("message") or "Дякую! Успіх."
        await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)

    except Exception as exc:
        LOGGER.error(f"Connection Failed: {exc}")
        await update.message.reply_text("⚠️ Помилка з'єднання.", reply_markup=ReplyKeyboardRemove())


# --- OTHER ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Діалог.")
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
        LOGGER.info(f"✅ БОТ @{me.username} ГОТОВИЙ")
        await application.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        LOGGER.warning(f"⚠️ Init warning: {e}")

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        api_base = get_api_base()
        LOGGER.info(f"🌍 API: {api_base}")

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


def get_bot_username() -> str:
    global _BOT_USERNAME
    if _BOT_USERNAME:
        return _BOT_USERNAME

    token = get_bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")

    url = f"{get_api_base()}{token}/getMe"
    try:
        resp = httpx.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        username = data.get("result", {}).get("username")
        if not username:
            raise RuntimeError("username missing in getMe response")
        _BOT_USERNAME = username
        return username
    except Exception as exc:
        LOGGER.error("get_bot_username failed: %s", exc)
        raise


def send_message_httpx(chat_id: str, text: str) -> None:
    token = get_bot_token()
    if not token:
        LOGGER.error("send_message_httpx skipped: TELEGRAM_BOT_TOKEN not configured")
        return

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    url = f"{get_api_base()}{token}/sendMessage"
    try:
        resp = httpx.post(url, json=payload, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        LOGGER.error("send_message_httpx failed: %s", exc)


def get_bot_status() -> dict:
    token = get_bot_token()
    status = {
        "token_present": bool(token),
        "username": _BOT_USERNAME,
    }

    if not token:
        status["status"] = "disabled"
        return status

    try:
        username = get_bot_username()
        status.update({
            "status": "ok",
            "username": username,
            "api_base": get_api_base(),
        })
    except Exception as exc:
        status["status"] = "error"
        status["error"] = str(exc)

    return status

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
