"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import sys
import time
import socket
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

# --- ЛОГУВАННЯ ---
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# Діагностика DNS при старті (щоб бачити, чи резолвиться Telegram)
try:
    LOGGER.info("DNS api.telegram.org => %s", socket.getaddrinfo("api.telegram.org", 443))
except Exception as e:
    LOGGER.warning("DNS Check failed: %s", e)

# --- КОНСТАНТИ ---
START_REPLY = "Вітаю я твій помічник від Helen Doron"
API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
API_URL_TEMPLATE = f"{API_BASE}/bot{{token}}/{{method}}"
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
    """Ледачо підвантажує .env один раз."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = os.getenv("ENV_FILE")
    env_file = Path(env_path) if env_path else _PROJECT_ROOT / ".env"

    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if not line or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except Exception as exc:
            LOGGER.warning("Не вдалося завантажити .env (%s): %s", env_file, exc)

    _ENV_LOADED = True

def get_bot_token() -> str:
    """Повертає токен бота, перевіряючи різні варіанти змінних."""
    _load_env_from_file_once()

    # Спроба читання з файлу (Docker secrets)
    file_candidates = [
        os.getenv("TELEGRAM_BOT_TOKEN_FILE"),
        os.getenv("BOT_TOKEN_FILE"),
    ]
    for file_path in file_candidates:
        if file_path:
            try:
                token = Path(file_path).read_text(encoding="utf-8").strip()
                if token: return token
            except FileNotFoundError:
                pass

    # Спроба читання змінних оточення
    candidates = [
        "TELEGRAM_BOT_TOKEN",
        "BOT_TOKEN",
        "TELEGRAM_TOKEN",
    ]
    for key in candidates:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()

    # Якщо нічого не знайдено, повертаємо порожній рядок (щоб не крашити весь апп одразу)
    # Але логуємо помилку
    LOGGER.error("TELEGRAM_BOT_TOKEN не знайдено!")
    return "" 

def get_bot_username() -> str:
    """Повертає username бота."""
    global _BOT_USERNAME
    _load_env_from_file_once()
    
    if _BOT_USERNAME: return _BOT_USERNAME
    
    # Спроба взяти з env
    username = os.getenv("BOT_USERNAME") or os.getenv("TELEGRAM_BOT_USERNAME")
    if username:
        _BOT_USERNAME = username
        return username

    # Якщо немає в env, можна спробувати запитати API (але це синхронний виклик)
    # Поки повертаємо placeholder, якщо API недоступне
    return "UnknownBot"


# --- HTTP UTILS ---

def telegram_api_request(method: str, payload: dict, *, timeout: float = 15.0, retries: int = 3) -> dict:
    """Прямий виклик API (для швидких перевірок)."""
    token = get_bot_token()
    if not token:
        raise RuntimeError("No token")
        
    url = API_URL_TEMPLATE.format(token=token, method=method)
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description"))
            return data
        except Exception as exc:
            last_error = exc
            LOGGER.warning("API attempt %s failed: %s", attempt, exc)
            time.sleep(1.5 * attempt)

    raise RuntimeError(last_error or "Unknown API error")

def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


# --- ХЕНДЛЕРИ ---

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.info(f"📩 /start від {update.effective_user.id}")
    if not update.message: return

    # Перевірка deep linking (наприклад t.me/bot?start=TOKEN)
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
    LOGGER.info(f"📩 Контакт від {update.effective_user.id}")
    if not update.message or not update.message.contact: return

    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text("Спершу відкрийте бота за посиланням.", reply_markup=ReplyKeyboardRemove())
        return

    contact = update.message.contact
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text("Поділіться ВЛАСНИМ номером.", reply_markup=ReplyKeyboardRemove())
        return

    # Відправка на Backend
    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": contact.phone_number,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(_link_callback_url(), json=payload)
            data = response.json()
    except Exception as exc:
        LOGGER.error(f"Link recovery failed: {exc}")
        await update.message.reply_text("⚠️ Помилка з'єднання з сервером.", reply_markup=ReplyKeyboardRemove())
        return

    bot_text = data.get("bot_text") or data.get("message") or "Готово."
    await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

    if data.get("status") == "ok":
        context.user_data.pop("link_token", None)


# --- CONVERSATION HANDLER ---

async def conversation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Діалог розпочато. /cancel для виходу.")
    return TYPING_REPLY

async def conversation_store_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Відповідь збережено.")
    return ConversationHandler.END

async def conversation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: await update.message.reply_text("Діалог скасовано.")
    return ConversationHandler.END

def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("dialog", conversation_entry)],
        states={TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_store_reply)]},
        fallbacks=[CommandHandler("cancel", conversation_cancel)],
    )

async def on_post_init(application: Application) -> None:
    """Викликається після успішного з'єднання."""
    try:
        me = await application.bot.get_me()
        LOGGER.info(f"✅ БОТ ГОТОВИЙ: @{me.username} (ID: {me.id})")
    except Exception as e:
        LOGGER.warning(f"⚠️ Post-init warning: {e}")


# --- ЗАПУСК ---

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        if not token:
            raise RuntimeError("Token not found")

        # Налаштування мережі (Збільшені тайм-аути)
        request_settings = HTTPXRequest(
            connect_timeout=60.0,
            read_timeout=60.0,
            write_timeout=60.0,
            connection_pool_size=10,
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
    """
    Головна точка входу. 
    Викликається з main.py в окремому потоці.
    """
    LOGGER.info("🚀 Ініціалізація Telegram бота...")

    while True:
        try:
            # 1. Перевіряємо базовий зв'язок (синхронно)
            try:
                telegram_api_request("getMe", {})
            except Exception as e:
                LOGGER.warning(f"⚠️ Немає зв'язку з Telegram API: {e}. Спроба запуску все одно...")

            # 2. Отримуємо application
            application = get_application()

            # 3. Запускаємо polling
            # ВАЖЛИВО: stop_signals=[] запобігає помилці "signal only works in main thread"
            application.run_polling(
                stop_signals=[], 
                close_loop=False,
                bootstrap_retries=-1,
                timeout=60,
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES,
            )
            # Якщо run_polling завершився нормально - виходимо
            break

        except Exception as exc:
            LOGGER.error("❌ Критична помилка бота: %s", exc)
            LOGGER.info("🔄 Автоматичний перезапуск через 10 секунд...")
            
            # Скидаємо application, щоб перестворити з'єднання
            global _application
            _application = None
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
