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

    # Перевірка центру (якщо логіка ще не готова)
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # 1. Отримуємо вхідні дані "як є" (лише прибираємо пробіли по краях)
        # Lower() для email - стандарт, бо пошта нечутлива до регістру
        input_email = body.email.strip().lower()
        # Пароль лишаємо чутливим до регістру!
        input_password = body.password.strip()

        print(f"LOGIN attempt for: {input_email}")

        # 2. Шукаємо користувача в базі
        # Отримуємо повний список (можна оптимізувати через фільтр, але так надійніше для початку)
        records = client.collection("user_staff").get_full_list()
        
        user = None
        for r in records:
            # Універсальне отримання даних з об'єкта PocketBase
            if hasattr(r, "model_dump"):
                data = r.model_dump()
            elif hasattr(r, "to_dict"):
                data = r.to_dict()
            else:
                data = getattr(r, "__dict__", {})

            # Порівнюємо email
            db_email = str(data.get("user_mail", "")).strip().lower()
            if db_email == input_email:
                user = data
                break

        if not user:
            print(f"❌ User not found for email: {input_email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # 3. Отримуємо пароль з бази
        db_password = str(user.get("user_pass", "")).strip()

        # 4. ПРЯМЕ ПОРІВНЯННЯ (Без нормалізацій)
        if db_password != input_password:
            # === БЛОК ВІДЛАДКИ (Тільки якщо пароль не підійшов) ===
            print("❌ Password Mismatch!")
            print(f"   DB Pass Length: {len(db_password)} | Input Pass Length: {len(input_password)}")
            
            # Виводимо коди символів, щоб бачити різницю (навіть для ієрогліфів)
            # Це покаже, якщо літери візуально однакові, але різні технічно
            print(f"   DB Codes:    {[ord(c) for c in db_password]}")
            print(f"   Input Codes: {[ord(c) for c in input_password]}")
            # ========================================================
            
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Якщо дійшли сюди - все добре
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
