# =====================================================
# FinDesk API - Production Dockerfile
# Python 3.14.2 + React + Vite Multi-Stage Build
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

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env.example .env.example

# Copy built frontend from stage 1
COPY --from=frontend-builder /build/dist ./frontend/dist

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Run application with Python 3.14 optimizations
# PEP 779: Free-threaded Python support
# PEP 649: Deferred annotation evaluation
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
