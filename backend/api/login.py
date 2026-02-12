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

    # Перевірка центру
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # 1. Отримуємо вхідні дані
        email = body.email.strip().lower()
        password_input = body.password.strip()
        
        print(f"LOGIN attempt for: {email}")

        # 2. Шукаємо користувача в базі
        records = client.collection("user_staff").get_full_list()
        user = None
        
        for r in records:
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
            print(f"❌ User not found for email: {email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # 3. Отримуємо пароль з бази
        raw_db_pass = str(user.get("user_pass", ""))

        # === FIX: Очищення від HTML-тегів ===
        # PocketBase Rich Text поле додає <p>...</p>, цей код їх видаляє
        password_db = re.sub(r'<[^>]+>', '', raw_db_pass).strip()

        # Для відладки (можна видалити пізніше)
        if raw_db_pass != password_db:
             print(f"⚠️ HTML tags removed from DB password. Raw: '{raw_db_pass}' -> Clean: '{password_db}'")

        # 4. Порівняння
        if password_db != password_input:
            print("❌ Password Mismatch even after cleaning!")
            # Якщо знову не підійде - виведемо коди, щоб точно знати причину
            print(f"   Clean DB Codes: {[ord(c) for c in password_db]}")
            print(f"   Input Codes:    {[ord(c) for c in password_input]}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        print("✅ Login successful")
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
