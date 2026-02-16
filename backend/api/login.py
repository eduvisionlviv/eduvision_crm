import hmac
import re
from typing import Optional

from appwrite.query import Query
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.appwrite import db

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    center: Optional[str] = None
    email: str
    password: str


@router.post("/login")
def login_user(body: LoginRequest):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="Appwrite client not available")

    try:
        email = body.email.strip().lower()
        password_input = body.password.strip()

        queries = [Query.equal("user_mail", [email]), Query.limit(1)]
        if body.center:
            queries.append(Query.equal("lc_id", [body.center]))

        result = client.list_documents(
            db.database_id,
            db.resolve_collection_id("user_staff"),
            queries,
        )

        users = result.get("documents", [])
        if not users:
            raise HTTPException(status_code=401, detail="Невірний email або пароль")

        user = users[0]

        raw_db_pass = str(user.get("user_pass", ""))
        password_db = re.sub(r"<[^>]+>", "", raw_db_pass).strip()

        if not hmac.compare_digest(password_db, password_input):
            raise HTTPException(status_code=401, detail="Невірний email або пароль")

        user.pop("user_pass", None)
        user["role"] = user.get("user_access", "staff")
        user["name"] = user.get("user_name", "Unknown")
        user["email"] = user.get("user_mail", email)

        return {
            "status": "ok",
            "collection": "user_staff",
            "token": user.get("$id"),
            "user": user,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера при вході")
