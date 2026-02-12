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

        # 2. Шукаємо користувача
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
        password_db = str(user.get("user_pass", "")).strip()

        # 4. Порівняння і ДІАГНОСТИКА
        if password_db != password_input:
            print("❌ Password Mismatch!")
            print(f"   DB Pass:    '{password_db}'") # Обережно, покаже пароль у логах!
            print(f"   Input Pass: '{password_input}'")
            
            # ОСЬ ЦЕ НАМ ПОТРІБНО:
            print(f"   DB Codes:    {[ord(c) for c in password_db]}")
            print(f"   Input Codes: {[ord(c) for c in password_input]}")
            
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
