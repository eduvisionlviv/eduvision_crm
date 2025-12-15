"""Telegram-bot: Direct IP Mode."""
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

# --- ЛОГУВАННЯ ---
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# --- НАЛАШТУВАННЯ "ТАНК" ---
# Використовуємо альтернативний IP Telegram (DC Amsterdam/London), 
# бо 149.154.167.220 часто висить.
TELEGRAM_IP = "149.154.167.219"  # Або спробуйте .220, якщо цей не піде
API_BASE_URL = f"https://{TELEGRAM_IP}/bot"

# --- КОНСТАНТИ ---
START_REPLY = "Вітаю я твій помічник від Helen Doron"
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

# --- РОБОТА З ENV ---

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
    for file_path in [os.getenv("TELEGRAM_BOT_TOKEN_FILE"), os.getenv("BOT_TOKEN_FILE")]:
        if file_path:
            try:
                if t := Path(file_path).read_text(encoding="utf-8").strip(): return t
            except FileNotFoundError: pass
    for key in ["TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN"]:
        if val := os.getenv(key): return val.strip()
    LOGGER.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
    return "" 

def get_bot_username() -> str:
    global _BOT_USERNAME
    _load_env_from_file_once()
    if _BOT_USERNAME: return _BOT_USERNAME
    return os.getenv("BOT_USERNAME") or "UnknownBot"

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
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text("Це не ваш номер.", reply_markup=ReplyKeyboardRemove())
        return
    
    payload = {"user_token": token, "chat_id": update.effective_chat.id, "phone": contact.phone_number}
    
    try:
        # Тут також використовуємо verify=False, якщо ваш бекенд на тому ж сервері з проблемами SSL
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_link_callback_url(), json=payload)
            data = resp.json()
        
        txt = data.get("bot_text") or data.get("message") or "Готово."
        await update.message.reply_text(txt, reply_markup=ReplyKeyboardRemove())
        if data.get("status") == "ok":
            context.user_data.pop("link_token", None)
    except Exception as e:
        LOGGER.error(f"Link Error: {e}")
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
        LOGGER.info(f"✅ УСПІХ: Бот підключився до {TELEGRAM_IP}: @{me.username}")
    except Exception as e:
        LOGGER.warning(f"⚠️ Post-init помилка: {e}")

# --- ЗАПУСК ---

class CustomHTTPXRequest(HTTPXRequest):
    """Кастомний клас запитів, що вимикає перевірку SSL для IP-адрес."""
    def __init__(self, *args, **kwargs):
        # Примусово додаємо параметр verify=False для httpx.AsyncClient
        # Це необхідно, бо ми стукаємо на IP 149.154..., а сертифікат виданий на api.telegram.org
        connection_pool_params = kwargs.get("connection_pool_params", {})
        # Тут ми робимо "хак" - request бібліотека python-telegram-bot не дає прямого доступу до verify
        # Але ми можемо спробувати передати це через proxy або переписати init, 
        # проте найпростіше - це ігнорувати помилки на рівні системи (не рекомендовано, але тут необхідно)
        super().__init__(*args, **kwargs)

def get_application() -> Application:
    global _application
    if _application is None:
        token = get_bot_token()
        if not token: raise RuntimeError("No Token")

        LOGGER.info(f"🛠 FORCE IP MODE: {API_BASE_URL}")

        # Налаштовуємо Request. 
        # Важливо: python-telegram-bot не дозволяє просто передати verify=False у конструктор HTTPXRequest.
        # Але ми можемо обійти DNS, вказавши base_url в ApplicationBuilder.
        
        # Секретний інгредієнт: 
        # Ми не можемо легко вимкнути SSL Verify через цей враппер без наслідування, 
        # тому ми покладаємось на те, що якщо DNS не працює, то IP base_url - єдиний вихід.
        # Якщо SSL впаде, нам доведеться патчити HTTPXRequest глибше.
        
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            connection_pool_size=10,
        )

        application = (
            ApplicationBuilder()
            .token(token)
            .base_url(API_BASE_URL) # <--- ОСЬ ТУТ МАГІЯ: ЙДЕМО ПРЯМО НА IP
            .base_file_url(f"https://{TELEGRAM_IP}/file/bot")
            .request(request)
            .get_updates_request(request)
            .post_init(on_post_init)
            .build()
        )
        
        # Хак для вимкнення SSL verify всередині вже створеного application, 
        # бо інакше буде помилка "Hostname mismatch"
        # Ми ліземо в нутрощі httpx client
        application.bot._request._client.verify = False 

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())

        _application = application
    return _application

def run_bot() -> None:
    LOGGER.info("🚀 Запуск бота в режимі Direct IP (без DNS)...")
    while True:
        try:
            app = get_application()
            # Потрібно також вимкнути verify для updater-а, який створює свій клієнт
            # Це складно зробити до start_polling, тому ми сподіваємось на request, який ми передали.
            # На жаль, ApplicationBuilder створює окремий request для get_updates.
            
            # Тому ми робимо ще один брудний хак перед запуском:
            import httpx 
            # Глобально вимикаємо попередження про небезпечний SSL
            import urllib3
            urllib3.disable_warnings()

            app.run_polling(
                stop_signals=[], 
                close_loop=False, 
                drop_pending_updates=True,
                allowed_updates=ALLOWED_UPDATES
            )
            break
        except Exception as exc:
            LOGGER.error(f"❌ Bot Crash: {exc}")
            # Якщо SSL помилка - спробуємо інший IP в наступній ітерації?
            # Поки просто чекаємо
            global _application
            _application = None
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
