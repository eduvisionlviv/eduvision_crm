"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

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

LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

START_REPLY = "Вітаю я твій помічник від Helen Doron"
# Дозволяємо замінити endpoint через TELEGRAM_API_BASE (наприклад, якщо DNS блокує api.telegram.org)
API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
API_URL_TEMPLATE = f"{API_BASE}/bot{{token}}/{{method}}"
BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"
LINK_INSTRUCTION = (
    "📱 Щоб підтвердити, що це саме ваш акаунт EduVision,\n"
    "будь ласка, поділіться своїм номером телефону, натиснувши кнопку нижче."
)

CHOOSING, TYPING_REPLY = range(2)

_application: Optional[Application] = None
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BOT_USERNAME: Optional[str] = None
ALLOWED_UPDATES = ["message", "contact", "callback_query"]

__all__ = ["run_bot", "get_application"]

def get_bot_token() -> str:
    """Повертає токен бота з підтримкою кількох назв змінних."""

    _load_env_from_file_once()

    file_candidates = [
        os.getenv("TELEGRAM_BOT_TOKEN_FILE"),
        os.getenv("BOT_TOKEN_FILE"),
        os.getenv("TELEGRAM_TOKEN_FILE"),
    ]
    for file_path in file_candidates:
        if file_path:
            try:
                token = Path(file_path).read_text(encoding="utf-8").strip()
                if token:
                    return token
            except FileNotFoundError:
                LOGGER.warning("Файл із токеном Telegram не знайдено: %s", file_path)

    candidates = [
        "TELEGRAM_BOT_TOKEN",
        "BOT_TOKEN",
        "TELEGRAM_TOKEN",
        "TELEGRAM_API_TOKEN",
        "TELEGRAM_BOT_API_TOKEN",
    ]

    for key in candidates:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()

    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN не задано. Вкажіть TELEGRAM_BOT_TOKEN (або BOT_TOKEN / TELEGRAM_TOKEN)."
    )


def _load_env_from_file_once() -> None:
    """Ледачо підвантажує .env один раз, щоб зчитати токен/username."""

    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = os.getenv("ENV_FILE")
    if env_path:
        env_file = Path(env_path)
    else:
        env_file = _PROJECT_ROOT / ".env"

    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if not line or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Не вдалося завантажити .env (%s): %s", env_file, exc)

    _ENV_LOADED = True


def telegram_api_request(method: str, payload: dict, *, timeout: float = 15.0, retries: int = 3) -> dict:
    """Викликає Telegram Bot API через httpx з повторними спробами."""

    token = get_bot_token()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description") or "Unknown Telegram error")
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            LOGGER.warning("Telegram API attempt %s/%s failed: %s", attempt, retries, exc)
            time.sleep(1.5 * attempt)

    raise RuntimeError(last_error or "Unknown Telegram API error")


# Синонім для зворотної сумісності і уникнення NameError у поточних лонгрunning-процесах
_telegram_api_request = telegram_api_request


def send_message_httpx(chat_id: int, text: str) -> bool:
    """Надсилає повідомлення через Bot API без запуску поллінгу."""

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        telegram_api_request("sendMessage", payload)
        return True
    except Exception as exc:
        LOGGER.error("Не вдалося надіслати повідомлення в Telegram: %s", exc)
        return False


def get_bot_username() -> str:
    """Повертає username бота або піднімає виняток із поясненням."""

    global _BOT_USERNAME
    _load_env_from_file_once()
    if not _BOT_USERNAME:
        _BOT_USERNAME = (
            os.getenv("BOT_USERNAME")
            or os.getenv("TELEGRAM_BOT_USERNAME")
            or os.getenv("TELEGRAM_USERNAME")
        )
    if _BOT_USERNAME:
        return _BOT_USERNAME

    token = get_bot_token()

    try:
        data = telegram_api_request("getMe", {})
        username = data.get("result", {}).get("username")
        if not username:
            raise RuntimeError("Bot API не повернув username")
        _BOT_USERNAME = username
        return username
    except Exception as exc:
        raise RuntimeError(f"Не вдалося отримати дані бота: {exc}") from exc


def get_bot_status() -> dict:
    """Повертає зрозумілий статус налаштування Telegram-бота."""

    try:
        token = get_bot_token()
    except RuntimeError as exc:
        return {
            "configured": False,
            "status": "missing_token",
            "message": str(exc),
        }

    status: dict = {"configured": True}

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
            proxy=os.getenv("TELEGRAM_PROXY"),
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
    LOGGER.info("🚀 Запуск Telegram бота... Входимо в режим очікування з'єднання...")

    while True:
        try:
            application = get_application()
            telegram_api_request("getMe", {})  # швидка перевірка токена/мережі
            application.run_polling(
                stop_signals=None,
                bootstrap_retries=-1,
                timeout=60,
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES,
            )
            break
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("❌ Збій з'єднання (DNS/Network): %s", exc)
            LOGGER.info("🔄 Перезапуск бота через 10 секунд...")
            # Якщо з'єднання обірвалося — відбудуємо application, щоб перезапустити HTTPX сесії
            global _application
            _application = None
            time.sleep(10)
