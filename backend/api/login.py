# backend/api/login.py
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    center: Optional[str] = None   # значення з селекту "Навчальний центр"
    email: str
    password: str


@router.post("/login")
def login_user(body: LoginRequest):
    """
    Якщо center порожній або 'Оберіть ваш центр...' → логін у Base‑колекції user_staff
    по полях user_mail / user_pass.
    Для інших центрів логіку додамо пізніше.
    """
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    # Поки що підтримуємо тільки сценарій "Оберіть ваш центр..."
    if body.center not in (None, "", "Оберіть ваш центр..."):
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # шукаємо користувача за user_mail
        records = client.collection("user_staff").get_full_list(
            filter=f"user_mail = '{body.email}'"
        )
        if not records:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user = records[0]

        # Порівнюємо пароль з поля user_pass
        stored_pass = user.get("user_pass")
        if stored_pass != body.password:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Тимчасовий "токен" – можна замінити на JWT пізніше
        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("id"),
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
