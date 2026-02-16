from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.login import router as login_router
from backend.api.universal_api import router as universal_router
from backend.environment import settings
from backend.services.appwrite import db
import asyncio
import os

app = FastAPI(title="CRM Eduvision API")
app.include_router(universal_router)
app.include_router(login_router)


@app.on_event("startup")
async def startup_event():
    print("🚀 Startup event викликано")

    required = {
        "APPWRITE_ENDPOINT": settings.APPWRITE_ENDPOINT,
        "APPWRITE_PROJECT_ID": settings.APPWRITE_PROJECT_ID,
        "APPWRITE_API_KEY": settings.APPWRITE_API_KEY,
        "APPWRITE_DATABASE_ID": settings.APPWRITE_DATABASE_ID,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        print(f"⚠️ Відсутні env для Appwrite: {', '.join(missing)}")

    try:
        await asyncio.wait_for(asyncio.to_thread(db.connect), timeout=10.0)
        print(
            f"✅ Appwrite статус: "
            f"{'підключено' if db.is_authenticated else 'не підключено, але API працює'}"
        )
    except asyncio.TimeoutError:
        print("⚠️ Timeout підключення до Appwrite, продовжуємо без БД")
    except Exception as e:
        print(f"❌ Помилка при підключенні до Appwrite: {e}")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "message": "API is running",
        "database_connected": db.is_authenticated,
        "database_provider": "appwrite",
    }


# Serve static files from frontend/dist
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Якщо шлях починається з api — не віддавати фронтенд
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}

        dist_path = "frontend/dist"
        file_path = os.path.join(dist_path, full_path)

        if os.path.isfile(file_path):
            return FileResponse(file_path)

        return FileResponse(os.path.join(dist_path, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "message": "CRM Eduvision API",
            "note": "Frontend not built.",
        }
