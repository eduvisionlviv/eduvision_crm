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

    # Якщо центр обраний, але логіка ще не готова, можна поки пропустити
    # або залишити перевірку, якщо ви хочете суворо контролювати це.
    # if body.center:
    #     pass 

    try:
        # 1. Отримуємо вхідні дані
        email = body.email.strip().lower()
        password_input = body.password.strip()

        # 2. ОПТИМІЗАЦІЯ: Шукаємо конкретного користувача через фільтр API
        # Замість завантаження всієї бази (get_full_list), беремо тільки одного
        try:
            record = client.collection("user_staff").get_first_list_item(f'user_mail="{email}"')
        except Exception:
            # Якщо запис не знайдено, PocketBase кине помилку (404)
            raise HTTPException(status_code=401, detail="Невірний email або пароль")

        # Конвертація об'єкта PocketBase у словник
        if hasattr(record, "model_dump"):
            user = record.model_dump()
        elif hasattr(record, "to_dict"):
            user = record.to_dict()
        else:
            # Fallback для старих версій клієнта
            user = getattr(record, "__dict__", {})
            # Чистка службових полів, якщо це __dict__
            if "collection_id" in user: 
                 # іноді __dict__ містить зайве, але для JSON це не критично
                 pass

        # 3. Отримуємо пароль з бази та очищаємо від HTML (Rich Text problem)
        raw_db_pass = str(user.get("user_pass", ""))
        password_db = re.sub(r'<[^>]+>', '', raw_db_pass).strip()

        # 4. Порівняння паролів
        if password_db != password_input:
            raise HTTPException(status_code=401, detail="Невірний email або пароль")

        # 5. ВАЖЛИВО: Нормалізація полів для фронтенду
        # Фронтенд чекає user.role, user.name, user.email
        user['role'] = user.get('user_access', 'staff')  # Мапимо user_access -> role
        user['name'] = user.get('user_name', 'Unknown')
        user['email'] = user.get('user_mail', email)

        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("id"), # Використовуємо ID як токен (або згенеруйте JWT, якщо є механізм)
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера при вході")
