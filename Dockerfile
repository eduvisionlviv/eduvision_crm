# 1. Використовуємо стабільний офіційний образ Python (Docker Hub)
# Він надійніший за Microsoft MCR, який зараз віддає 403 помилку
FROM python:3.10-slim

# Встановлюємо робочу директорію
WORKDIR /app

# 2. Встановлюємо системні бібліотеки, які потрібні для Chromium/Playwright
# Робимо це від імені ROOT під час збірки. Це вирішує проблему "su: Authentication failure"
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnss3-dev \
    libxss-dev \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libnspr4 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. Створюємо звичайного користувача (безпека + вимога платформ типу Hugging Face)
RUN useradd -m -u 1000 user

# 4. Встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Встановлюємо Playwright Chromium (ПОКИ МИ ЩЕ ROOT)
# Це критичний момент: браузер ставиться глобально, і права доступу будуть правильними.
RUN playwright install chromium
# install-deps про всяк випадок, хоча ми вже поставили пакети вручну в кроці 2
RUN playwright install-deps chromium 

# 6. Копіюємо весь код проекту
# Одразу передаємо права нашому користувачу "user"
COPY --chown=user:user . /app

# 7. Перемикаємось на безпечного користувача
USER user

# Налаштовуємо змінні середовища
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Відкриваємо порт
EXPOSE 7860

# 8. Запуск сервера
# --timeout 120 дає більше часу на "холодний старт", щоб уникнути падінь
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120", "--workers", "1", "--threads", "8"]
