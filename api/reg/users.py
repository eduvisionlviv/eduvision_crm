# api/reg/users.py
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache
from api.login.join import hash_password
import secrets
import logging
import datetime as dt

bp = Blueprint("reg_user", __name__, url_prefix="/api")
log = logging.getLogger("reg.users")

@bp.post("/reg_user")
def reg_user():
    """
    approve: Створює користувача в contacts (заповнюючи всі обов'язкові поля) і видаляє заявку.
    reject:  Додає email в black_list (якщо таблиця є) і видаляє заявку.
    """
    data = request.json or {}
    action = data.get("action")
    row_id = data.get("id")

    if not row_id or action not in ("approve", "reject"):
        return jsonify(error="invalid_args"), 400

    contacts = get_client_for_table("contacts")
    register = get_client_for_table("register")
    black_list = get_client_for_table("black_list")

    # 1. Отримуємо заявку з register
    try:
        # Шукаємо по $id (системний ID Appwrite)
        reg_row = register.table("register").select("*").eq("$id", row_id).single().execute().data
        if not reg_row:
            # Фолбек: іноді фронт шле старий ID, пробуємо знайти по кастомному полю, якщо воно є
            reg_row = register.table("register").select("*").eq("id", row_id).single().execute().data
    except Exception as e:
        log.error(f"Read register failed: {e}")
        return jsonify(error="read_failed"), 500

    if not reg_row:
        return jsonify(error="not_found"), 404

    email = reg_row.get("user_email")
    name = reg_row.get("user_name")
    phone = reg_row.get("user_phone")

    # ───────────────────────── REJECT (Відхилити) ─────────────────────────
    if action == "reject":
        # Спроба додати в Blacklist
        try:
            # Перевіряємо, чи вже там є
            exists = black_list.table("black_list").select("user_email").eq("user_email", email).execute().data
            if not exists:
                black_list.table("black_list").insert({
                    "user_email": email,
                    "user_name": name,
                    "user_phone": phone,
                    "data": dt.datetime.utcnow().isoformat()
                }).execute()
        except Exception as e:
            # Якщо таблиці немає або інша помилка — просто логуємо, але не ламаємо процес видалення
            log.warning(f"Blacklist insert failed (maybe table missing?): {e}")

        # Видаляємо заявку
        try:
            register.table("register").delete().eq("$id", row_id).execute()
        except Exception as e:
            log.error(f"Register delete failed: {e}")
            return jsonify(error="delete_failed"), 500

        return jsonify(status="ok", action="reject")

    # ───────────────────────── APPROVE (Схвалити) ─────────────────────────
    if action == "approve":
        # Перевірка дублікатів в contacts
        exists = contacts.table("contacts").select("user_id").eq("user_email", email).execute().data
        if exists:
            # Якщо юзер вже є, просто видаляємо заявку
            register.table("register").delete().eq("$id", row_id).execute()
            return jsonify(error="duplicate", message="Користувач вже існує"), 409

        # Підготовка даних для contacts (user_admin)
        # ВАЖЛИВО: Заповнюємо всі REQUIRED поля з вашої таблиці
        new_user_data = {
            "user_email": email,
            "user_name": name,
            "user_phone": phone or "-",
            "pass_email": reg_row.get("pass_email"),
            
            # Обов'язкові системні поля
            "user_access": "student",        # role
            "user_id": secrets.token_hex(8), # userId (унікальний рядок)
            "is_active": True,               # isActive
            "recovery_tg_id": "-",           # user_tg_id (заглушка)
            "auth_tokens": "-",              # auth_tokens (заглушка)
            # Необов'язкові, але корисні
            "expires_at": None,
            "last_login": None
        }

        # Хешування паролю, якщо він прийшов "чистим"
        pwd = new_user_data["pass_email"]
        if pwd and not pwd.startswith("$2"):
            new_user_data["pass_email"] = hash_password(pwd)

        try:
            # Створення користувача
            res = contacts.table("contacts").insert(new_user_data).execute()
            
            if res.data:
                # Успіх - видаляємо заявку з register
                register.table("register").delete().eq("$id", row_id).execute()
                clear_cache("contacts")
                return jsonify(status="ok", created_id=res.data.get("user_id")), 200
            else:
                return jsonify(error="insert_failed"), 500
        except Exception as e:
            log.error(f"Approve failed: {e}")
            return jsonify(error="server_error", detail=str(e)), 500
