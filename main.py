import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()

# ─── API (Ваш майбутній бекенд) ───
@app.get("/api/health")
async def health_check():
    return {"status": "active", "system": "EduVision CRM"}

# ─── FRONTEND (React + Vite) ───
# Важливо: Vite збирає проект у папку 'dist' (стандарт). 
# Якщо у вас налаштовано інакше - змініть цю назву.
STATIC_DIR = "dist" 

if os.path.exists(STATIC_DIR):
    # 1. Підключаємо папку assets (JS, CSS, картинки), щоб вони вантажилися швидко
    app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

    # 2. SPA Catch-all: Всі інші запити віддають index.html
    # Це дозволяє React Router керувати переходами по сторінках (напр. /dashboard, /login)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Перевіряємо, чи існує такий фізичний файл (наприклад favicon.ico)
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Якщо файлу немає - віддаємо index.html (React розбереться сам)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    print(f"⚠️ УВАГА: Папка '{STATIC_DIR}' не знайдена. Виконується в режимі 'API Only' або ще не було білда.")

if __name__ == "__main__":
    # Coolify передає порт через змінну оточення, або 8080 за замовчуванням
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
