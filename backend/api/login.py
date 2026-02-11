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
    Якщо center порожній або 'Оберіть ваш центр...' → логін у Base-колекції user_staff
    по полях user_mail / user_pass.
    Для інших центрів логіку додамо пізніше.
    """
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    # Поки що: як тільки явно обрано якийсь центр (не плейсхолдер) – блочимо.
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # 1) Витягуємо всі записи з user_staff
        records = client.collection("user_staff").get_full_list()

        # 2) Шукаємо по полю user_mail
        user = None
        for r in records:
            # r у Python-SDK PocketBase – це dict-подібний об'єкт [web:42][web:48]
            if r.get("user_mail") == body.email:
                user = r
                break

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # 3) Перевіряємо пароль з поля user_pass
        stored_pass = user.get("user_pass")
        if stored_pass != body.password:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("id"),  # тимчасовий "токен"
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
