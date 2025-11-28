"""Telegram-бот на основі `python-telegram-bot` з додатковими клієнтами.

Основний цикл обробки оновлень працює на `python-telegram-bot` (PTB), що дає
готові механізми `JobQueue`, `ConversationHandler` та інші сучасні можливості.

На додачу ми тримаємо ледачо створений клієнт `telebot.TeleBot` (модуль пакета
`pyTelegramBotAPI`) для простих синхронних викликів із інших частин бекенду.
Для повної сумісності залишено і низькорівневий HTTP-шар на основі ``httpx``.

Наразі бот завжди відповідає на команду `/start` фразою
``"Вітаю я твій помічник від Helen Doron"``. Також присутні шаблони для
майбутніх сценаріїв: повторювана задача в `JobQueue` та мінімальний
`ConversationHandler`, який можна розширювати під потреби клієнта.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import httpx
from telebot import TeleBot
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    JobQueue,
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

__all__ = [
    "START_REPLY",
    "run_bot",
    "get_bot_token",
    "get_bot_username",
    "get_application",
    "get_telebot",
    "send_message_httpx",
]


def get_bot_token() -> str:
    """Читає токен бота з ``TELEGRAM_BOT_TOKEN``."""

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")
    return token


def get_bot_username() -> str:
    """Повертає username Telegram-бота, викликаючи getMe при потребі."""

    global _BOT_USERNAME
    if _BOT_USERNAME:
        return _BOT_USERNAME

    token = get_bot_token()
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                API_URL_TEMPLATE.format(token=token, method="getMe"),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            username = data.get("result", {}).get("username")
    except Exception as exc:  # pragma: no cover - мережевий код
        raise RuntimeError("Не вдалося отримати username Telegram-бота") from exc

    if not username:
        raise RuntimeError("Telegram API не повернув username для бота")

    _BOT_USERNAME = username
    return username


def _link_callback_url() -> str:
    base = BACKEND_URL.rstrip("/")
    return f"{base}{LINK_RECOVERY_PATH}"


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє `/start` і, за необхідності, пропонує поділитися телефоном."""

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
    """Передає контакт у бекенд для валідації телефону користувача."""

    if not update.message or not update.message.contact:
        return

    token = context.user_data.get("link_token")
    if not token:
        await update.message.reply_text(
            "Спершу відкрийте бота за персональним посиланням із EduVision.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    contact = update.message.contact
    if contact.user_id and update.effective_user and contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "Будь ласка, поділіться власним номером через кнопку нижче.",
            reply_markup=ReplyKeyboardRemove(),
        )
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
    except Exception as exc:  # pragma: no cover - лише логування
        LOGGER.exception("link_recovery call failed: %s", exc)
        await update.message.reply_text(
            "⚠️ Сталася помилка. Спробуйте ще раз пізніше.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    bot_text = data.get("bot_text") or data.get("message") or "Готово."
    await update.message.reply_text(bot_text, reply_markup=ReplyKeyboardRemove())

    if data.get("status") == "ok":
        context.user_data.pop("link_token", None)


async def conversation_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Стартує демонстраційний діалог, який можна розширювати."""

    if update.message:
        await update.message.reply_text(
            "Це шаблон розмови. Напишіть відповідь або скористайтеся /cancel."
        )
    return TYPING_REPLY


async def conversation_store_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Зберігає відповідь користувача у user_data і завершує діалог."""

    if update.message:
        context.user_data["last_reply"] = update.message.text
        await update.message.reply_text(
            "Дякую! Ваша відповідь збережена. Ви можете повторити команду «/dialog»."
        )
    return ConversationHandler.END


async def conversation_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Дозволяє користувачеві вийти з діалогу."""

    if update.message:
        await update.message.reply_text("Розмову скасовано.")
    context.user_data.clear()
    return ConversationHandler.END


def build_conversation_handler() -> ConversationHandler:
    """Створює мінімальний ConversationHandler для майбутніх сценаріїв."""

    return ConversationHandler(
        entry_points=[CommandHandler("dialog", conversation_entry)],
        states={
            TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_store_reply)],
        },
        fallbacks=[CommandHandler("cancel", conversation_cancel)],
        allow_reentry=True,
    )


async def scheduled_heartbeat(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проста періодична задача JobQueue (можна замінити на бізнес-логіку)."""

    job = context.job
    LOGGER.info("JobQueue heartbeat відпрацював (job=%s, data=%s)", job.name, job.data)


def configure_jobqueue(job_queue: JobQueue) -> None:
    """Налаштовує базові задачі JobQueue."""

    # Перевірку інтервалу можна буде змінити через конфіг або env
    job_queue.run_repeating(
        scheduled_heartbeat,
        interval=3600,
        first=3600,
        name="heartbeat",
        data={"note": "приклад періодичної задачі"},
    )


def get_application() -> Application:
    """Створює (або повертає кешований) застосунок PTB."""

    global _application
    if _application is None:
        token = get_bot_token()
        application = Application.builder().token(token).build()

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(build_conversation_handler())

        configure_jobqueue(application.job_queue)
        _application = application
    return _application


def get_telebot() -> TeleBot:
    """Ледаче створення клієнта telebot для синхронних викликів."""

    global _telebot
    if _telebot is None:
        _telebot = TeleBot(get_bot_token(), parse_mode="HTML")
    return _telebot


def send_message_httpx(chat_id: int, text: str) -> None:
    """Пряме звернення до Telegram API через httpx (низькорівневий варіант)."""

    token = get_bot_token()
    with httpx.Client() as client:
        response = client.post(
            API_URL_TEMPLATE.format(token=token, method="sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        response.raise_for_status()


def run_bot() -> None:
    """Синхронний вхід для запуску бота в окремому треді."""

    application = get_application()

    # Ініціалізуємо telebot заздалегідь, щоб перехопити можливі помилки конфігурації
    get_telebot()

    try:
        application.run_polling(stop_signals=None)
    except KeyboardInterrupt:
        LOGGER.info("Telegram-бот зупинено користувачем")
    except Exception:  # pragma: no cover - лише для логування у продакшені
        LOGGER.exception("Telegram-бот завершився з помилкою")
        raise


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        LOGGER.info("Бот зупинено користувачем")
        sys.exit(0)
