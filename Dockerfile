# Використовуємо офіційний образ Playwright (там вже є браузери та Python)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Робоча директорія
WORKDIR /app

# Копіюємо requirements та встановлюємо бібліотеки
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Створюємо користувача (вимога безпеки Hugging Face)
RUN useradd -m -u 1000 user

# Копіюємо весь код проекту і надаємо права користувачу
COPY --chown=user . /app

# Перемикаємось на користувача
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Hugging Face вимагає порт 7860
EXPOSE 7860

# Запускаємо через Gunicorn. 
# Увага: у вас файл main.py, тому пишемо "main:app"
CMD ["gunicorn", "-b", "0.0.0.0:7860", "main:app", "--timeout", "120"]
