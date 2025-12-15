"""Telegram-бот на основі python-telegram-bot."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

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
ALLOWED_UPDATES = ["message", "contact"]
_application: Optional[Application] = None
_ENV_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─────────────── PROXY SETUP ───────────────
def _setup_proxy_env():
    """
    Примусово дублює налаштування проксі в усі змінні оточення,
    щоб httpx точно їх побачив.
    """
    system_proxy = (
        os.getenv("TELEGRAM_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
    )
    
    if system_proxy:
        # Дублюємо проксі для всіх варіантів написання
        os.environ["HTTP_PROXY"] = system_proxy
        os.environ["HTTPS_PROXY"] = system_proxy
        os.environ["http_proxy"] = system_proxy
        os.environ["https_proxy"] = system_proxy
        LOGGER.info(f"✅ Proxy environment configured: {system_proxy}")
        return system_proxy
    return None

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

# ─────────────── TELEGRAM API (httpx) ───────────────
def telegram_api_request(
    method: str,
    payload: dict,
    *,
    timeout: float = 20.0,
    retries: int = 3,
) -> dict:
    token = get_bot_token()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            # Створюємо клієнт БЕЗ аргументів проксі.
            # trust_env=True (за замовчуванням) змусить його читати os.environ['HTTPS_PROXY'],
            # який ми налаштували в _setup_proxy_env()
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    raise RuntimeError(data)
                return data
        except Exception as e:
            last_error = e
            LOGGER.warning("Telegram API attempt %s/%s failed: %s", attempt, retries, e)
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
        await update.message.reply_text("Спершу відкрийте бота за посиланням.", reply_markup=ReplyKeyboardRemove())
        return
    payload = {
        "user_token": token,
        "chat_id": update.effective_chat.id,
        "phone": update.message.contact.phone_number,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(BACKEND_URL.rstrip("/") + LINK_RECOVERY_PATH, json=payload)
            data = r.json()
    except Exception as e:
        LOGGER.error("link_recovery error: %s", e)
        await update.message.reply_text("⚠️ Помилка сервера.", reply_markup=ReplyKeyboardRemove())
        return
    await update.message.reply_text(data.get("bot_text", "Готово."), reply_markup=ReplyKeyboardRemove())

# ─────────────── APPLICATION ───────────────
def get_application() -> Application:
    global _application
    if _application:
        return _application
    token = get_bot_token()
    
    # Тут ми теж НЕ передаємо proxy_url, покладаючись на env vars
    # Але якщо дуже треба - можна розкоментувати
    request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
    )

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
    LOGGER.info(f"🚀 Запуск Telegram бота (httpx v{httpx.__version__})...")
    
    # Налаштовуємо середовище перед запуском
    _setup_proxy_env()

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
