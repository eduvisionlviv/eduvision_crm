import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("main")

# Lifespan: Керування запуском та зупинкою фонових процесів
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Starting services (Telegram, Playwright)...")
    # Тут виклики запуску фонових задач, наприклад:
    # asyncio.create_task(my_background_task())
    yield
    log.info("🛑 Shutting down services...")
    # Тут код для очистки ресурсів

app = FastAPI(lifespan=lifespan)

# CORS: Дозволи для фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Для продакшену замініть "*" на ваш домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API ───
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "system": "FastAPI + React"}

# Сюди згодом підключіть ваші переписані API модулі:
# app.include_router(users.router, prefix="/api/users")


# ─── FRONTEND (React + Vite) ───
# Вказуємо папку з білдом. Перевірте vite.config.ts -> build.outDir (зазвичай 'dist' або 'web')
STATIC_DIR = "web" 

if os.path.exists(STATIC_DIR):
    # Обслуговування статичних файлів (js, css, img)
    app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

    # SPA Catch-all: Перенаправляє всі інші запити на index.html (для React Router)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    log.warning(f"⚠️ Папка '{STATIC_DIR}' не знайдена! Запустіть 'npm run build'.")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # host="0.0.0.0" обов'язковий для Coolify/Docker
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
