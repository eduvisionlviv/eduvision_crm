# backend/api/login.py
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.pocketbase import db
import json

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
        input_email = body.email.strip().lower()
        input_password = body.password.strip()

        print(f"\n🕵️‍♂️ --- DEEP DEBUG START for: {input_email} ---")

        # Отримуємо всіх (можна оптимізувати, але для тесту надійніше так)
        records = client.collection("user_staff").get_full_list()
        
        user = None
        for r in records:
            # Конвертація в словник (dict)
            if hasattr(r, "model_dump"):
                data = r.model_dump()
            elif hasattr(r, "to_dict"):
                data = r.to_dict()
            else:
                data = getattr(r, "__dict__", {})

            # Перевіряємо email
            # Тут ми явно бачимо, з якого поля беремо пошту
            db_email = str(data.get("user_mail", "")).strip().lower()
            
            if db_email == input_email:
                user = data
                print(f"✅ USER FOUND! ID: {data.get('id')}")
                
                # === 1. ВИВОДИМО СТРУКТУРУ БАЗИ ===
                print(f"📂 RECORD KEYS (Columns available): {list(data.keys())}")
                
                # === 2. ЩО МИ ВИТЯГУЄМО ===
                raw_pass = data.get("user_pass")
                print(f"🧐 EXTRACTING field 'user_pass': '{raw_pass}' (Type: {type(raw_pass)})")
                
                # Перевіримо, чи немає випадково поля 'password'
                if "password" in data:
                    print(f"⚠️ FOUND field 'password': '{data.get('password')}' (Maybe we should use this?)")
                
                break

        if not user:
            print(f"❌ User not found in DB loop.")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # === 3. ПОРІВНЯННЯ ===
        db_password = str(user.get("user_pass", "")).strip()
        
        if db_password != input_password:
            print("❌ PASSWORD MISMATCH DETECTED")
            print(f"   Input ('{input_password}') vs DB ('{db_password}')")
            
            # ASCII коди (щоб побачити приховані символи)
            print(f"   DB Codes:    {[ord(c) for c in db_password]}")
            print(f"   Input Codes: {[ord(c) for c in input_password]}")
            
            raise HTTPException(status_code=401, detail="Invalid email or password")

        print("✅ LOGIN SUCCESS")
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
