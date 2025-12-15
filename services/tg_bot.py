"""Telegram-бот з примусовим DNS-патчем."""
from __future__ import annotations

import logging
import os
import sys
import time
import socket
from pathlib import Path
from typing import Optional

# --- 🛠 ЯДЕРНИЙ ФІКС DNS (Monkey Patch) ---
# Це вирішує проблему [Errno -5] No address associated with hostname
# Ми вручну кажемо Python, що api.telegram.org — це 149.154.167.220

REAL_TELEGRAM_IP = "149.154.167.220"
_original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Підміна DNS запиту тільки для Telegram."""
    try:
        if isinstance(host, str) and "api.telegram.org" in host:
            # Повертаємо хардкодом IP адресу Telegram
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (REAL_TELEGRAM_IP, 443))]
    except Exception:
        pass
    # Для всіх інших сайтів працюємо як завжди
    return _original_getaddrinfo(host, port, family, type, proto, flags)

# Застосовуємо патч
socket.getaddrinfo = patched_getaddrinfo
# ------------------------------------------

import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
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

LOGGER.info(f"💉 DNS Patch застосовано: api.telegram.org -> {REAL_TELEGRAM_IP}")

# --- КОНСТАНТИ ---
START_REPLY = "Вітаю я твій помічник від Helen Doron"
# Важливо: лишаємо api.telegram.org, бо наш патч вище перехопить це ім'я
API_BASE = "https://api.telegram.org/bot" 
BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"
LINK_INSTRUCTION = (
    "📱 Щоб підтвердити, що це саме ваш акаунт EduVision,\n",
    "будь ласка, поділіться своїм номером телефону, натиснувши кнопку нижче."
)

CHOOSING, TYPING_REPLY = range(2)
ALLOWED_UPDATES = ["message", "contact", "callback_query"]

_application: Optional[Application] = None
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BOT_USERNAME: Optional[str] = None

__all__ = ["run_bot", "get_application", "get_bot_token"]


# --- РОБОТА З ENV ТА ТОКЕНАМИ ---

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
    # 1. Файл
    for file_path in [os.getenv("TELEGRAM_BOT_TOKEN_FILE"), os.getenv("BOT_TOKEN_FILE")]:
        if file_path:
            try:
                token = Path(file_path).read_text(encoding="utf-8").strip()
                if token: return token
            except FileNotFoundError: pass
    # 2. Env
    for key in ["TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN"]:
        val = os.getenv(key)
        if val and val.strip(): return val.strip()
    
    LOGGER.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
    return "" 

def get_bot_username() -> str:
    global _BOT_USERNAME
    _load_env_from_file_once()
    if _BOT_USERNAME: return _BOT_USERNAME
    return os.getenv("BOT_USERNAME") or "UnknownBot"

# --- HTTP UTILS (DIRECT) ---

def telegram_api_request(method: str, payload: dict, *, timeout: float = 15.0) -> dict:
    """Прямий виклик API (використовує пропатчений socket)."""
    token = get_bot_token()
    if not token: return {}
        
    url = f"{API_BASE}{token}/{method}"
    
    # Використовуємо httpx, він підтягне наш socket.getaddrinfo
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        LOGGER.warning(f"Direct API check failed: {exc}")
        raise

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


# --- ХЕНДЛЕРИ ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    raw = context.args[0] if context.args else None
    token = raw.replace("-", ".") if raw else None

    if token:
        context.user_data["link_token"] = token
        markup = ReplyKeyboardMarkup(
            [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(LINK_INSTRUCTION, reply_markup=markup)
    else:
        await update.message.reply_text(START_REPLY)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.contact: return

    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text("Спершу відкрийте бота за посиланням.", reply_markup=ReplyKeyboardRemove())
        return

    contact = update.message.contact
    # Проста перевірка свій/чужий
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text("Це не ваш номер.", reply_markup=ReplyKeyboardRemove())
        return

    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_link_callback_url(), json=payload)
            data = resp.json()
        
        txt = data.get("bot_text") or data.get("message") or "Готово."
        await update.message.reply_text(txt, reply_markup=ReplyKeyboardRemove())
        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)

    except Exception as e:
        LOGGER.error(f"Backend error: {e}")
        await update.message.reply_text("Помилка з'єднання.", reply_markup=ReplyKeyboardRemove())

# --- CONVERSATION ---
async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Діалог. /cancel для виходу.")
    return TYPING_REPLY

async def conversation_store_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Збережено.")
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

async def on_post_init(application: Application) -> None:
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅ Telegram Connected: @{me.username}")
    except Exception as e:
        LOGGER.warning(f"⚠️ Post-init check failed: {e}")

# --- ЗАПУСК ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        if not token: raise RuntimeError("No Token")

        # Налаштування HTTPX
        # Збільшуємо тайм-аути, бо DNS патч може додавати затримок на старті
        req_settings = HTTPXRequest(
            connect_timeout=40.0,
            read_timeout=40.0,
            write_timeout=40.0,
            connection_pool_size=10,
        )

        application = (
            ApplicationBuilder()
            .token(token)
            .request(req_settings)
            .get_updates_request(req_settings)
            .post_init(on_post_init)
            .build()
        )

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())

        _application = application
    return _application

def run_bot() -> None:
    """Точка входу для main.py"""
    LOGGER.info("🚀 Запуск бота з обходом DNS...")
    
    while True:
        try:
            # Спроба прямого запиту (перевірка патча)
            try:
                telegram_api_request("getMe", {})
            except Exception:
                LOGGER.warning("⚠️ Прямий тест провалився, але пробуємо запустити Polling...")

            app = get_application()
            
            # stop_signals=[] важливий для запуску в потоці
            app.run_polling(
                stop_signals=[], 
                close_loop=False,
                bootstrap_retries=-1,
                timeout=60,
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES
            )
            break
        except Exception as e:
            LOGGER.error(f"❌ Bot Crash: {e}")
            global _application
            _application = None
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
