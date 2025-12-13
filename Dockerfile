# Використовуємо офіційний образ Playwright (в ньому вже є браузери!)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Робоча папка
WORKDIR /app

# Копіюємо requirements
COPY requirements.txt requirements.txt

# Встановлюємо залежності Python
RUN pip install --no-cache-dir -r requirements.txt

# Створюємо користувача (вимога безпеки Hugging Face)
RUN useradd -m -u 1000 user

# Копіюємо весь код і віддаємо права юзеру
COPY --chown=user . /app

# Перемикаємось на юзера
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Hugging Face очікує порт 7860
EXPOSE 7860

# Запускаємо через Gunicorn (вказуємо main:app, бо ваш файл main.py)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120"]
