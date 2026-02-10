# Eduvision CRM

## Опис проєкту

Система управління навчальним закладом з React фронтендом та Python (FastAPI) бекендом.

## Швидкий старт

### Локальна розробка з Docker

Збудуйте Docker образ:
```bash
docker build -t eduvision-crm .
```

Запустіть контейнер:
```bash
docker run -p 3000:3000 eduvision-crm
```

Відкрийте в браузері: [http://localhost:3000](http://localhost:3000)

API доступне через `/api/` (наприклад, `/api/health`)

### Деплой на Coolify

1. У Coolify створіть новий проєкт
2. Підключіть цей GitHub репозиторій
3. Виберіть тип деплою: **Dockerfile**
4. Вкажіть порт: **3000**
5. Coolify автоматично збудує і запустить контейнер

### Архітектура

- **Frontend**: React + TypeScript + Vite (порт 3000)
- **Backend**: FastAPI + Uvicorn (порт 8000, доступний через `/api`)
- **Веб-сервер**: Nginx (проксує запити)
- **Оркестрація**: Supervisord (керує nginx та uvicorn)

Все працює в одному Docker контейнері.

## Розробка

Для локальної розробки можна використовувати docker-compose (якщо присутній):
```bash
docker-compose up
```
