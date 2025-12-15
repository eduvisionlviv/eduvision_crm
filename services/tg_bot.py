import asyncio
import logging
import time
import os
import sys

# Імпорти Telegram
from telegram import Update, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)
from telegram.request import HTTPXRequest

# --- НАЛАШТУВАННЯ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отримуємо токен із змінних середовища (те, що ви налаштували в Secrets)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- 🔌 ФУНКЦІЯ-МОСТОК ДЛЯ MAIN.PY ---
def get_bot_token():
    """Цю функцію викликає main.py, щоб перевірити, чи є токен."""
    return TOKEN

# --- 1. ТУТ ВАШІ ФУНКЦІЇ (ХЕНДЛЕРИ) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start"""
    user = update.effective_user
    await update.message.reply_html(
        rf"Вітаю, {user.mention_html()}! Я працюю стабільно 🚀"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help"""
    await update.message.reply_text("Я готовий до роботи. Моя мережа налаштована.")

async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приклад відповіді на текст (ехо)"""
    await update.message.reply_text(f"Ви написали: {update.message.text}")


# --- 2. ЛОГІКА ЗАПУСКУ (SYSTEM CORE) ---
async def run_bot_logic():
    """Налаштування та запуск бота."""
    
    if not TOKEN:
        logger.error("❌ Токен не знайдено! Перевірте Secrets.")
        return

    # Посилені налаштування мережі (HTTPXRequest)
    trequest = HTTPXRequest(
        connection_pool_size=20, 
        connect_timeout=30.0,    
        read_timeout=30.0,
        write_timeout=30.0
    )

    # Ініціалізація Application
    application = Application.builder().token(TOKEN).request(trequest).build()

    # --- 3. РЕЄСТРАЦІЯ ХЕНДЛЕРІВ ---
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Додаємо обробку тексту (щоб бот не мовчав)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
    
    # Встановлення меню команд
    await application.bot.set_my_commands([
        BotCommand("start", "Запуск"),
        BotCommand("help", "Допомога"),
    ])

    logger.info(f"🚀 Бот запускається з токеном: {TOKEN[:5]}***")
    
    # Ініціалізація та старт
    await application.initialize()
    await application.start()
    
    # Запуск polling
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Тримаємо процес живим
    stop_signal = asyncio.Event()
    await stop_signal.wait()

    # Коректна зупинка
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

# --- 4. ЗАХИСТ ВІД ПАДІННЯ (WATCHDOG) ---
def start_bot_process():
    """Ця функція перезапускає бота, якщо він впаде."""
    retry_count = 0
    while True:
        try:
            # Створюємо чистий Event Loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if retry_count > 0:
                logger.warning(f"🔄 Рестарт бота (Спроба #{retry_count})")
            
            loop.run_until_complete(run_bot_logic())
            
        except Exception as e:
            logger.error(f"❌ Бот впав з помилкою: {e}")
            logger.error("⏳ Чекаємо 10 секунд...")
            time.sleep(10)
            retry_count += 1
        finally:
            try:
                loop.close()
            except:
                pass

if __name__ == "__main__":
    start_bot_process()
