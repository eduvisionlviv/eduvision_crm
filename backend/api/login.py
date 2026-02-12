# backend/api/login.py
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    center: Optional[str] = None
    email: str
    password: str


@router.post("/login")
def login_user(body: LoginRequest):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    # Перевірка центру (заготовка на майбутнє)
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # 1. Отримуємо вхідні дані
        email = body.email.strip().lower()
        password_input = body.password.strip()

        # 2. Шукаємо користувача в базі
        records = client.collection("user_staff").get_full_list()
        user = None
        
        for r in records:
            # Конвертація об'єкта PocketBase у словник
            if hasattr(r, "model_dump"):
                data = r.model_dump()
            elif hasattr(r, "to_dict"):
                data = r.to_dict()
            else:
                data = getattr(r, "__dict__", {})

            db_email = str(data.get("user_mail", "")).strip().lower()
            if db_email == email:
                user = data
                break

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # 3. Отримуємо пароль з бази та очищаємо від HTML (Rich Text problem)
        raw_db_pass = str(user.get("user_pass", ""))
        password_db = re.sub(r'<[^>]+>', '', raw_db_pass).strip()

        # 4. Порівняння
        if password_db != password_input:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("id"),
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        # У продакшн коді traceback краще писати в файл логів, а не в консоль
        raise HTTPException(status_code=500, detail=str(e))
