# api/reg/users.py
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache
from api.login.join import hash_password
import secrets
import logging
import datetime as dt

bp = Blueprint("reg_user", __name__, url_prefix="/api")
log = logging.getLogger("reg.users")

AUTH_TTL_HOURS = 168

@bp.post("/reg_user")
def reg_user():
    data = request.json or {}
    action = (data.get("action") or "").lower()
    row_id = data.get("id")
    auto_login = bool(data.get("auto_login"))

    if action not in ("approve", "reject") or not row_id:
        return jsonify({"error": "invalid_args"}), 400

    contacts = get_client_for_table("contacts")
    register = get_client_for_table("register")
    black_list = get_client_for_table("black_list")

    # 1. Читаємо заявку
    try:
        # Шукаємо за $id
        reg_row = register.table("register").select("*").eq("$id", row_id).single().execute().data
    except Exception: reg_row = None

    if not reg_row: return jsonify({"error": "not_found"}), 404

    email = reg_row.get("user_email")
    name = reg_row.get("user_name")
    phone = reg_row.get("user_phone")

    # --- REJECT ---
    if action == "reject":
        # Спроба додати в Blacklist (якщо таблиця існує)
        try:
            exists = black_list.table("black_list").select("user_email").eq("user_email", email).execute().data
            if not exists:
                black_list.table("black_list").insert({
                    "user_email": email,
                    "user_name": name,
                    "user_phone": phone,
                    "data": dt.datetime.utcnow().isoformat()
                }).execute()
        except Exception as e:
            log.warning(f"Blacklist insert skipped: {e}")

        # Видалення
        register.table("register").delete().eq("$id", row_id).execute()
        return jsonify({"status": "ok", "action": "reject"})

    # --- APPROVE ---
    try:
        exists = contacts.table("contacts").select("user_id").eq("user_email", email).execute().data
        if exists:
            register.table("register").delete().eq("$id", row_id).execute()
            return jsonify({"error": "duplicate"}), 409

        # Підготовка полів для contacts (Враховано всі обов'язкові поля!)
        pwd = reg_row.get("pass_email")
        if not pwd.startswith("$2"): pwd = hash_password(pwd)

        new_user = {
            "user_email": email,
            "user_name": name,
            "user_phone": phone or "-",
            "pass_email": pwd,
            
            # Обов'язкові системні поля (як на вашому скріншоті)
            "user_access": "student",        # role
            "user_id": secrets.token_hex(8), # userId (унікальний рядок)
            "is_active": True,               # isActive
            "recovery_tg_id": "-",           # user_tg_id
            "auth_tokens": "-",              # auth_tokens (заглушка)
            "expires_at": None,
            "last_login": None
        }

        if auto_login:
            new_user["auth_tokens"] = secrets.token_urlsafe(32)
            # expires_at заповниться null або датою, якщо треба

        ins = contacts.table("contacts").insert(new_user).execute()
        
        # Видаляємо з register тільки після успішного insert
        if ins.data:
            register.table("register").delete().eq("$id", row_id).execute()
            
            out = {"status": "ok", "action": "approve", "created_id": ins.data.get("user_id")}
            if auto_login:
                out["auth_tokens"] = new_user["auth_tokens"]
            return jsonify(out), 200
        else:
            return jsonify({"error": "insert_failed"}), 500

    except Exception as e:
        log.error(f"Approve error: {e}")
        return jsonify({"error": "internal_error"}), 500
