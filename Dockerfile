# Використовуємо образ Playwright (де вже є браузери)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Встановлюємо залежності
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- ВИПРАВЛЕННЯ ---
# Користувач з ID 1000 вже існує (pwuser). Ми просто використовуємо його.
COPY --chown=pwuser . /app

# Перемикаємось на існуючого юзера
USER pwuser
ENV HOME=/home/pwuser \
    PATH=/home/pwuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Порт для Hugging Face
EXPOSE 7860

# Запуск
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120"]
