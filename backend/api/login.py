import hmac
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.teable import db

router = APIRouter(prefix="/api", tags=["auth"])

class LoginCredentials(BaseModel):
    email: str
    password: str

@router.post("/login")
def login_pipeline(body: LoginCredentials):
    if not db.get_client():
        raise HTTPException(status_code=500, detail="Teable client not available")

    email = body.email.strip().lower()
    password_input = body.password.strip()

    # Крок 1: Перевірка Credentials в Auth_Accounts
    result = db.list_records(table="Auth_Accounts", full_list=True)
    users = [u for u in result.get("items", []) if str(u.get("email", "")).strip().lower() == email]
    
    if not users:
        raise HTTPException(status_code=401, detail="Невірний email або пароль")
    user = users[0]

    password_db = re.sub(r"<[^>]+>", "", str(user.get("password_hash", ""))).strip()
    if not hmac.compare_digest(password_db, password_input):
        raise HTTPException(status_code=401, detail="Невірний email або пароль")

    # Крок 2: Перевірка заморозки (frozen_at)
    if user.get("frozen_at") or not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Акаунт заморожено. Зверніться до адміністратора.")

    role = user.get("role_id", "staff")
    
    # Крок 3: Визначення доступних центрів (Employee_LC_Access)
    if role in ["Tech_Admin", "MF_Admin"]:
        available_centers = [{"id": "network", "name": "Мережевий Дашборд (Всі центри)"}]
    else:
        access_records = db.list_records(table="Employee_LC_Access", full_list=True).get("items", [])
        user_access = [a for a in access_records if a.get("employee_id") == user["id"]]
        
        lc_records = db.list_records(table="Learning_Centres", full_list=True).get("items", [])
        
        available_centers = []
        for access in user_access:
            lc = next((l for l in lc_records if l["id"] == access["lc_id"]), None)
            if lc and lc.get("status") != "frozen":
                available_centers.append({
                    "id": lc["id"], 
                    "name": lc.get("lc_name", "Unknown"),
                    "is_primary": access.get("is_primary", False)
                })

    if not available_centers:
         raise HTTPException(status_code=403, detail="Немає доступу до жодного активного центру.")

    # Сортуємо: primary центр перший
    available_centers.sort(key=lambda x: x.get("is_primary", False), reverse=True)

    user.pop("password_hash", None)

    return {
        "status": "ok",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": role,
            "language": user.get("preferred_language", "uk")
        },
        "available_centers": available_centers,
        "requires_lc_selection": len(available_centers) > 1 and role not in ["Tech_Admin", "MF_Admin"]
    }
