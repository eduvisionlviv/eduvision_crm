from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ВИПРАВЛЕНО: Імпортуємо саме з папки services
from backend.services.pocketbase import db

app = FastAPI(title="CRM Eduvision API")

@app.on_event("startup")
async def startup_event():
    db.connect()

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "API is running",
        "database_connected": db.is_authenticated
    }

# Serve static files from frontend/dist
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Захист: якщо шлях починається з api, не віддавати фронтенд
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
            "note": "Frontend not built."
        }
