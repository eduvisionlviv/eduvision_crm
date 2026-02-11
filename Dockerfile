# =====================================================
# CRM Eduvision - Production Dockerfile
# =====================================================

# ==================== Stage 1: Build Frontend ====================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy frontend files
COPY frontend/package*.json ./
RUN npm install --prefer-offline --no-audit

COPY frontend/ ./
RUN npm run build

# ==================== Stage 2: Python Application ====================
FROM python:3.14.2-slim

# 1. Робоча директорія - корінь проекту всередині контейнера
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 2. Копіюємо папку backend
COPY backend/ ./backend/

# 3. Копіюємо зібраний фронтенд
COPY --from=frontend-builder /build/dist ./frontend/dist

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 4. Запускаємо сервер (шлях: backend.main:app)
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
