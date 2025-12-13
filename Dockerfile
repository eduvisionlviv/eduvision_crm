# 1. Фіксуємо версію Debian (bookworm = стабільна), щоб пакети не зникали
FROM python:3.10-slim-bookworm

# Встановлюємо робочу директорію
WORKDIR /app

# 2. Оновлюємо систему і ставимо тільки мінімум для збірки
# Прибираємо довгий список бібліотек, які викликали помилку
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 3. Створюємо користувача (безпека)
RUN useradd -m -u 1000 user

# 4. Встановлюємо Python-залежності (включаючи Playwright)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. МАГІЯ: Доручаємо Playwright самому встановити системні бібліотеки
# Флаг --with-deps автоматично підтягне правильні версії libatk, libgtk і т.д.
RUN playwright install --with-deps chromium

# 6. Копіюємо код проекту і передаємо права
COPY --chown=user:user . /app

# 7. Перемикаємось на користувача
USER user

# Налаштовуємо середовище
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Порт
EXPOSE 7860

# 8. Запуск
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120", "--workers", "1", "--threads", "8"]
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
