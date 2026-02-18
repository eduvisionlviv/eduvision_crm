import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.login import router as login_router
from backend.api.universal_api import router as universal_router
from backend.environment import settings
from backend.services.teable import db

app = FastAPI(title="CRM Eduvision API")
app.include_router(universal_router)
app.include_router(login_router)


@app.on_event("startup")
async def startup_event():
    print("🚀 Startup event викликано")

    required = {
        "TEABLE_BASE_URL": settings.TEABLE_BASE_URL,
        "TEABLE_API_TOKEN": settings.TEABLE_API_TOKEN,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        print(f"⚠️ Відсутні env для Teable: {', '.join(missing)}")

    try:
        await asyncio.wait_for(asyncio.to_thread(db.connect), timeout=10.0)
        print(
            f"✅ Teable статус: "
            f"{'підключено' if db.is_authenticated else 'не підключено, але API працює'}"
        )
    except asyncio.TimeoutError:
        print("⚠️ Timeout підключення до Teable, продовжуємо без БД")
    except Exception as e:
        print(f"❌ Помилка при підключенні до Teable: {e}")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "message": "API is running",
        "database_connected": db.is_authenticated,
        "database_provider": "teable",
    }


# Serve static files from frontend/dist
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
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
