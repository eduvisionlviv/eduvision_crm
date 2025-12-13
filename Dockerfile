FROM python:3.10-slim-bookworm

WORKDIR /app

# 1. Встановлюємо системні бібліотеки ВРУЧНУ (як ROOT)
# Ми робимо це тут, щоб не використовувати "playwright install-deps", який ламається
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Створюємо користувача
RUN useradd -m -u 1000 user

# 3. Налаштовуємо спільну папку для браузерів
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH

# 4. Встановлюємо Python залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Встановлюємо Chromium (як ROOT)
# Увага: тут немає команди install-deps!
RUN playwright install chromium

# 6. Передаємо права на папку браузерів нашому користувачу
RUN chown -R user:user $PLAYWRIGHT_BROWSERS_PATH

# 7. Копіюємо код додатка
COPY --chown=user:user . /app

# 8. Перемикаємось на юзера для безпеки
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

EXPOSE 7860

# Запуск
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120", "--workers", "1", "--threads", "8"]
