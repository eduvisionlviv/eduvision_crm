# backend/api/login.py
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    center: Optional[str] = None   # назва навчального центру з фронта
    email: str
    password: str


@router.post("/login")
def login_user(body: LoginRequest):
    """
    Якщо center == 'Оберіть ваш центр...' → шукаємо в user_staff.
    Інакше (тимчасово) – у reg.
    """
    client = db.get_client()

    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    if body.center is None or body.center == "Оберіть ваш центр...":
        collection_name = "user_staff"
    else:
        collection_name = "reg"

    # Переконуємось, що колекція існує (як у universal_api)
    from backend.api.universal_api import ensure_collection_exists

    ensure_collection_exists(collection_name)

    # ⚠️ Це логін через кастомну колекцію, НЕ admin
    try:
        auth = client.collection(collection_name).auth_with_password(
            body.email,
            body.password,
        )
        # Повертаємо токен і базову інформацію
        return {
            "status": "ok",
            "collection": collection_name,
            "token": auth.token,
            "user": auth.record,
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid credentials: {e}")
