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

    # дозволяємо "" і "Оберіть ваш центр..."
    if body.center and body.center != "Оберіть ваш центр...":
        raise HTTPException(
            status_code=400,
            detail="Логін для вибраного навчального центру ще не реалізований",
        )

    try:
        # нормалізуємо те, що прийшло з фронта
        email = body.email.strip().lower()
        password = body.password.strip()
        print("LOGIN attempt:", email, password)

        # читаємо всіх співробітників
        records = client.collection("user_staff").get_full_list()

        user = None
        for r in records:
            if hasattr(r, "model_dump"):
                data = r.model_dump()
            elif hasattr(r, "to_dict"):
                data = r.to_dict()
            else:
                data = getattr(r, "__dict__", {})

            print("PB record:", data)

            db_email = str(data.get("user_mail", "")).strip().lower()
            if db_email == email:
                user = data
                break

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        db_pass = str(user.get("user_pass", "")).strip()
        print("DB_PASS:", repr(db_pass), "INPUT_PASS:", repr(password))
        if db_pass != password:
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
