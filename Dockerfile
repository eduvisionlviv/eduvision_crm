# 1. Використовуємо офіційний образ Playwright
# В ньому вже встановлені браузери та системні бібліотеки
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# 2. Встановлюємо Python-пакети від імені ROOT
# Це важливо: якщо ставити їх як юзер, можуть бути проблеми з шляхами (PATH)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Копіюємо код додатка і одразу передаємо права власності
# pwuser вже існує в цьому образі Microsoft
COPY --chown=pwuser:pwuser . /app

# 4. Створюємо папку для даних, якщо вона потрібна (наприклад, для логів)
# і даємо права юзеру
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app/data

# 5. Перемикаємось на безпечного користувача
USER pwuser

# 6. Налаштовуємо змінні середовища
ENV HOME=/home/pwuser \
    PATH=/home/pwuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    # Важливо: кажемо Playwright не шукати браузери в системних папках,
    # а використовувати ті, що в образі
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

EXPOSE 7860

# 7. Запуск (збільшив timeout, щоб Gunicorn не вбивав процеси при довгому старті)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120", "--workers", "1", "--threads", "8"]
