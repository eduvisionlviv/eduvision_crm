import asyncio
import logging
import time
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Твій токен (бажано брати з змінних середовища, але поки лишаємо як є або встав сюди свій механізм отримання)
# ЗАМІНИ ЦЕЙ РЯДОК НА СВІЙ МЕТОД ОТРИМАННЯ ТОКЕНА, ЯКЩО ВІН ІНШИЙ
import os
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE_IF_NOT_ENV")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Привіт, {user.mention_html()}! Бот працює стабільно."
    )

async def run_bot_logic():
    """Основна логіка запуску бота з налаштуваннями мережі."""
    
    # 1. Налаштування запитів. Збільшуємо тайм-аути для повільних мереж.
    trequest = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=20.0, # Даємо 20 секунд на підключення
        read_timeout=20.0,    # Даємо 20 секунд на відповідь
        write_timeout=20.0
    )

    # 2. Створення додатку
    application = Application.builder().token(TOKEN).request(trequest).build()

    # 3. Додавання хендлерів
    application.add_handler(CommandHandler("start", start_command))

    # 4. Запуск (Polling)
    # drop_pending_updates=True, щоб бот не спамив відповідями на старі команди після перезапуску
    logger.info("🚀 Спроба з'єднання з Telegram API...")
    await application.initialize()
    await application.start()
    
    # Це запустить постійне опитування. 
    # Updater.start_polling() в нових версіях робиться через application.updater
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Тримаємо бота запущеним доки не буде зупинки
    # Використовуємо Event, щоб не блокувати потік наглухо
    stop_signal = asyncio.Event()
    await stop_signal.wait()

    # Коректне завершення (якщо дійдемо сюди)
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

def start_bot_process():
    """Функція-обгортка для запуску в окремому потоці/процесі."""
    retry_count = 0
    while True:
        try:
            # Створюємо новий Event Loop для кожної спроби
            # Це вирішує проблему 'Event loop is closed'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            logger.info(f"🔄 Запуск циклу бота (Спроба {retry_count + 1})...")
            loop.run_until_complete(run_bot_logic())
            
        except Exception as e:
            logger.error(f"❌ Критична помилка бота: {e}")
            logger.error("Перезапуск через 10 секунд...")
            time.sleep(10)
            retry_count += 1
        finally:
            try:
                loop.close()
            except:
                pass

if __name__ == "__main__":
    start_bot_process()
