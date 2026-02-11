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

# 1. Залишаємо стандартну директорію /app (так надійніше)
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

# 2. Копіюємо папку backend всередину /app
# Тепер шлях буде /app/backend/main.py
COPY backend/ ./backend/
COPY .env.example .env.example

# 3. Копіюємо фронтенд у /app/frontend/dist
# Це важливо, щоб бекенд міг знайти ці файли
COPY --from=frontend-builder /build/dist ./frontend/dist

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 4. ВИПРАВЛЕНО: запускаємо backend.main:app (а не app.main)
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
