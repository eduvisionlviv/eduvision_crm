# =====================================================
# CRM Eduvision - Production Dockerfile
# =====================================================

# ----------------- Stage 1: Build Frontend -----------------
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# 1. Копіюємо конфіги пакетів
COPY frontend/package*.json ./

# 2. Встановлюємо залежності
RUN npm install --prefer-offline --no-audit

# 3. Копіюємо весь код фронтенду
COPY frontend/ ./

# 4. Збираємо проект (створюється папка dist)
RUN npm run build

# ----------------- Stage 2: Python Backend -----------------
FROM python:3.14.2-slim

# Робоча папка в контейнері
WORKDIR /app

# Встановлюємо системні утиліти
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо Python залежності
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копіюємо код бекенду
COPY backend/ ./backend/

# --- ГОЛОВНИЙ МОМЕНТ ---
# Копіюємо готовий фронтенд з першого етапу в папку, де його чекає Python
COPY --from=frontend-builder /build/dist ./frontend/dist

# Створюємо місце для бази даних
RUN mkdir -p /app/data

EXPOSE 8080

# Перевірка здоров'я
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Запуск сервера
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
