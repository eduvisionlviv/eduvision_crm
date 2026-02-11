# =====================================================
# CRM Eduvision - Dev/Stage Dockerfile
# =====================================================

# --- ЕТАП 1: Фронтенд (ЗАКОМЕНТОВАНО ДО ПОЯВИ ФАЙЛІВ) ---
# Як тільки заллєте React-файли, розкоментуйте цей блок:
# FROM node:20-alpine AS frontend-builder
# WORKDIR /build
# COPY frontend/package*.json ./
# RUN npm install --prefer-offline --no-audit
# COPY frontend/ ./
# RUN npm run build

# ==================== Stage 2: Python Backend ====================
FROM python:3.14.2-slim

# Робоча папка
WORKDIR /app

# Системні залежності
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python залежності
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копіюємо бекенд
COPY backend/ ./backend/

# --- ІНТЕГРАЦІЯ ФРОНТЕНДУ (ЗАКОМЕНТОВАНО) ---
# Розкоментуйте цей рядок, коли розкоментуєте ЕТАП 1:
# COPY --from=frontend-builder /build/dist ./frontend/dist

# Папка для даних
RUN mkdir -p /app/data

# Порт
EXPOSE 8080

# Перевірка здоров'я
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Запуск
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
