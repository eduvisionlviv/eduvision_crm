# backend/api/login.py
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
        # 1. Отримуємо дані від користувача
        email = body.email.strip().lower()
        password_input = body.password.strip()
        
        print(f"LOGIN attempt for: {email}")

        # 2. Шукаємо користувача в базі
        records = client.collection("user_staff").get_full_list()
        user = None
        
        for r in records:
            # Отримуємо словник даних незалежно від типу об'єкта
            data = r.model_dump() if hasattr(r, "model_dump") else (r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}))
            
            db_email = str(data.get("user_mail", "")).strip().lower()
            if db_email == email:
                user = data
                break

        if not user:
            print("User not found")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # 3. Отримуємо пароль з бази
        password_db = str(user.get("user_pass", "")).strip()

        # === ГОЛОВНЕ ВИПРАВЛЕННЯ ===
        # Функція для заміни кириличної 'і' на латинську 'i'
        def normalize_pass(text: str) -> str:
            return text.replace("і", "i").replace("І", "I")

        # Порівнюємо нормалізовані версії
        if normalize_pass(password_db) != normalize_pass(password_input):
            print(f"Password mismatch even after normalization.")
            # Для глибокої відладки (можна видалити потім):
            # print(f"DB codes: {[ord(c) for c in password_db]}")
            # print(f"Input codes: {[ord(c) for c in password_input]}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        # ===========================

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
