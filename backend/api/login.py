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

    # Поки що: якщо явно вибрано якийсь центр (не порожній рядок і не None) – блочимо.
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # шукаємо користувача за user_mail так само, як у universal_api
        filter_str = f"user_mail = '{body.email}'"
        page_res = client.collection("user_staff").get_list(
            page=1,
            per_page=1,
            filter=filter_str,
        )
        items = page_res.items if hasattr(page_res, "items") else []

        if not items:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user = items[0]

        stored_pass = user.get("user_pass")
        if stored_pass != body.password:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Тимчасовий "токен" – поки що id запису, потім можна замінити на JWT
        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("id"),
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
