"""Telegram-bot with Business Logic & Cloudflare Mirror Support."""
from __future__ import annotations

import logging
import os
import sys
import time
import socket
from pathlib import Path
from typing import Optional

# --- 💉 DNS HARDFIX (Лікуємо сліпоту сервера Hugging Face) ---
# Ми вручну кажемо Python, що будь-який workers.dev — це IP Cloudflare.
CF_IP = "104.21.80.1" 
_original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host and "workers.dev" in str(host):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (CF_IP, 443))]
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo
# ------------------------------------------------

import httpx
# Додаємо підтримку telebot для сумісності з вашим старим кодом, якщо треба
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

# --- КОНСТАНТИ БІЗНЕС-ЛОГІКИ ---
START_REPLY = "Вітаю я твій помічник від Helen Doron"
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
    """Отримує токен з пріоритетом: файл -> змінні середовища."""
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
    """Повертає адресу API. Якщо задано TELEGRAM_API_BASE — використовує її (Mirror Mode)."""
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


# --- БІЗНЕС-ЛОГІКА (ХЕНДЛЕРИ) ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє /start. Якщо є токен (deep linking) — просить телефон."""
    if not update.message: return

    # Перевірка аргументів (наприклад t.me/bot?start=TOKEN)
    raw = context.args[0] if context.args else None
    token = raw.replace("-", ".") if raw else None

    if token:
        context.user_data["link_token"] = token
        markup = ReplyKeyboardMarkup(
            [[KeyboardButton("Поділитися телефоном ☎️", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(LINK_INSTRUCTION, reply_markup=markup)
        return

    await update.message.reply_text(START_REPLY)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отримує контакт, перевіряє його і відправляє на бекенд."""
    if not update.message or not update.message.contact: return

    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text(
            "Спершу відкрийте бота за персональним посиланням.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    contact = update.message.contact
    # Захист: чи це контакт самого користувача?
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "Будь ласка, поділіться ВЛАСНИМ номером (кнопка внизу).",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number,
    }

    try:
        # Тут також використовуємо збільшений timeout для надійності
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_link_callback_url(), json=payload)
            data = resp.json()
        
        bot_text = data.get("bot_text") or data.get("message") or "Готово."
        await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)
            
    except Exception as exc:
        LOGGER.error(f"Link Recovery Error: {exc}")
        await update.message.reply_text("⚠️ Помилка з'єднання з сервером.", reply_markup=ReplyKeyboardRemove())


# --- ДІАЛОГИ (CONVERSATION) ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Це демо-діалог. Напишіть щось або /cancel.")
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

# --- JOB QUEUE (ПЕРІОДИЧНІ ЗАДАЧІ) ---

async def scheduled_heartbeat(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    # Тут можна додати логіку, наприклад, пінгу бекенду
    # LOGGER.info(f"Heartbeat job: {job.data}")

def configure_jobqueue(job_queue: JobQueue) -> None:
    job_queue.run_repeating(
        scheduled_heartbeat,
        interval=3600,
        first=60,
        data="alive_check"
    )

async def on_post_init(application: Application) -> None:
    """Викликається після успішного з'єднання з Telegram."""
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅ БОТ ГОТОВИЙ ДО РОБОТИ: @{me.username} (ID: {me.id})")
        LOGGER.info(f"🔗 Режим дзеркала: {'АКТИВНИЙ' if 'workers.dev' in application.bot.base_url else 'ВИМКНЕНО'}")
    except Exception as e:
        LOGGER.warning(f"⚠️ Post-init check warning: {e}")


# --- SETUP & LAUNCH ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        if not token: raise RuntimeError("No Token found in ENV")

        api_base = get_api_base()
        LOGGER.info(f"🌍 Використовую адресу API: {api_base}")

        # Налаштування HTTP-клієнта (збільшені тайм-аути для стабільності)
        request = HTTPXRequest(
            connect_timeout=40.0,
            read_timeout=40.0,
            write_timeout=40.0,
            connection_pool_size=10,
        )

        application = (
            ApplicationBuilder()
            .token(token)
            .base_url(api_base)  # <--- Ключовий момент для Cloudflare
            .request(request)
            .get_updates_request(request)
            .post_init(on_post_init)
            .build()
        )

        # Реєстрація хендлерів
        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())
        
        # Налаштування черги задач
        configure_jobqueue(application.job_queue)

        _application = application
    return _application

# Додатковий метод для сумісності, якщо десь в коді використовується telebot
def get_telebot() -> TeleBot:
    global _telebot
    if _telebot is None:
        _telebot = TeleBot(get_bot_token(), parse_mode="HTML")
    return _telebot

def run_bot() -> None:
    """Головна функція запуску (entry point)."""
    LOGGER.info("🚀 Ініціалізація бота з повною бізнес-логікою...")
    
    # Вимикаємо шум від urllib3 (через проксі можуть бути попередження)
    import urllib3
    urllib3.disable_warnings()

    while True:
        try:
            app = get_application()
            
            # Запускаємо в режимі Polling
            # stop_signals=[] важливий для запуску в окремому потоці (як у вас в main.py)
            app.run_polling(
                stop_signals=[], 
                close_loop=False, 
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES
            )
            break
        except Exception as exc:
            LOGGER.error(f"❌ Bot Crash: {exc}")
            LOGGER.info("🔄 Автоматичний перезапуск через 10 секунд...")
            global _application
            _application = None
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
