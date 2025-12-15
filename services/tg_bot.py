"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple, Dict

import httpx
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

API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
API_URL_TEMPLATE = f"{API_BASE}/bot{{token}}/{{method}}"

BACKEND_URL = os.getenv("URL", "http://127.0.0.1:5000")
LINK_RECOVERY_PATH = "/api/tg/link_recovery"

LINK_INSTRUCTION = (
    "📱 Щоб підтвердити, що це саме ваш акаунт EduVision,\n"
    "будь ласка, поділіться своїм номером телефону, натиснувши кнопку нижче."
)

CHOOSING, TYPING_REPLY = range(2)
ALLOWED_UPDATES = ["message", "contact"]

_application: Optional[Application] = None
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BOT_USERNAME: Optional[str] = None

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


def _get_proxy_config() -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """
    Повертає (proxies_dict, proxy_url) для налаштування httpx.
    """
    # Шукаємо проксі у змінних оточення (Hugging Face завжди їх там має)
    proxy = (
        os.getenv("HTTPS_PROXY") 
        or os.getenv("https_proxy") 
        or os.getenv("HTTP_PROXY") 
        or os.getenv("http_proxy")
    )
    
    if not proxy:
        return None, None

    # httpx.post очікує словник 'proxies'
    proxies_dict = {
        "http://": proxy,
        "https://": proxy,
    }
    
    # HTTPXRequest очікує рядок 'proxy_url'
    return proxies_dict, proxy


# ─────────────── TELEGRAM API (httpx) ───────────────
def telegram_api_request(
    method: str,
    payload: dict,
    *,
    timeout: float = 20.0,
    retries: int = 3,
) -> dict:
    """
    Виконує прямий запит до Telegram API (для перевірки getMe).
    """
    token = get_bot_token()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    
    # Отримуємо налаштування проксі
    proxies_dict, _ = _get_proxy_config()

    if proxies_dict:
        LOGGER.info(f"🌐 Використовую проксі для запиту {method}")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            # Використовуємо аргумент 'proxies' (множина), це стандарт для httpx
            r = httpx.post(url, json=payload, timeout=timeout, proxies=proxies_dict)
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(data)
            return data
        except Exception as e:
            last_error = e
            LOGGER.warning(
                "Telegram API attempt %s/%s failed: %s",
                attempt,
                retries,
                e,
            )
            time.sleep(1.5 * attempt)

    raise RuntimeError(last_error)


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
        await update.message.reply_text(
            "Спершу відкрийте бота за спеціальним посиланням.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": update.message.contact.phone_number,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                BACKEND_URL.rstrip("/") + LINK_RECOVERY_PATH,
                json=payload,
            )
            data = r.json()
    except Exception as e:
        LOGGER.error("link_recovery error: %s", e)
        await update.message.reply_text(
            "⚠️ Помилка сервера.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await update.message.reply_text(
        data.get("bot_text", "Готово."),
        reply_markup=ReplyKeyboardRemove(),
    )


# ─────────────── APPLICATION ───────────────
def get_application() -> Application:
    global _application
    if _application:
        return _application

    token = get_bot_token()
    
    # Отримуємо проксі для бота
    _, proxy_url = _get_proxy_config()
    
    # Створюємо request з явним проксі
    # Використовуємо proxy_url (це стандарт для python-telegram-bot v20+)
    request_kwargs = {
        "connect_timeout": 60,
        "read_timeout": 60,
        "write_timeout": 60,
    }
    
    if proxy_url:
        request_kwargs["proxy_url"] = proxy_url
        
    request = HTTPXRequest(**request_kwargs)

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
    LOGGER.info("🚀 Запуск Telegram бота...")

    while True:
        try:
            telegram_api_request("getMe", {})
            app = get_application()
            app.run_polling(
                stop_signals=None,
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES,
            )
            break
        except Exception as e:
            LOGGER.error("❌ Telegram connection failed: %s", e)
            global _application
            _application = None
            time.sleep(10)
