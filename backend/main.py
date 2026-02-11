from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="CRM Eduvision API")

# API routes
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "API is running"}

# Serve static files from frontend/dist (after build)
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for all routes (SPA)
        dist_path = "frontend/dist"
        file_path = os.path.join(dist_path, full_path)
        
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Return index.html for all other routes
        return FileResponse(os.path.join(dist_path, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "message": "CRM Eduvision API",
            "note": "Frontend not built. Run 'cd frontend && npm run build' to build the frontend."
        }
