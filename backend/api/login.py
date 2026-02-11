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
    Якщо center порожній або 'Оберіть ваш центр...' → шукаємо в user_staff.
    Інакше – у reg (тимчасова логіка).
    """
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    # Визначаємо колекцію
    if not body.center or body.center == "Оберіть ваш центр...":
        collection_name = "user_staff"
    else:
        collection_name = "reg"

    try:
        # auth_with_password працює тільки для auth‑колекцій
        auth = client.collection(collection_name).auth_with_password(
            body.email,
            body.password,
        )
    except Exception as e:
        # 401 замість 500, щоб фронт бачив «неправильний логін/пароль»
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "status": "ok",
        "collection": collection_name,
        "token": auth.token,
        "user": auth.record,
    }
