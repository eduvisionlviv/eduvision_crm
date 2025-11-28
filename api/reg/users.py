# api/reg/users.py
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache
from api.login.join import hash_password
import os, secrets, datetime as dt, logging

bp = Blueprint("reg_user", __name__, url_prefix="/api")
log = logging.getLogger("reg.users")

AUTH_TTL_HOURS = int(os.getenv("AUTH_TTL_HOURS", "168"))

def _exp_iso():
    return (dt.datetime.utcnow() + dt.timedelta(hours=AUTH_TTL_HOURS)) \
           .replace(microsecond=0).isoformat() + "+00:00"


def _delete_register_row(register_client, row_id, user_email) -> bool:
    """
    Надійне видалення заявки з register:
      1) пробуємо delete by id;
      2) перевіряємо, чи зник;
      3) якщо ні — delete by user_email (на випадок type-місмеча id);
      4) фінальна перевірка.
    Повертає True, якщо запис відсутній після спроб.
    """
    # 1) delete by id
    try:
        register_client.table("register").delete().eq("id", row_id).execute()
    except Exception as e:
        log.warning("reject: delete by id failed (id=%s): %s", row_id, e)

    # перевірка
    try:
        still = register_client.table("register").select("id").eq("id", row_id).execute().data
    except Exception as e:
        log.warning("reject: recheck by id failed (id=%s): %s", row_id, e)
        still = None

    if not still:
        return True  # зник

    # 2) fallback: delete by email
    try:
        register_client.table("register").delete().eq("user_email", user_email).execute()
    except Exception as e:
        log.error("reject: delete by email failed (%s): %s", user_email, e)

    # фінальна перевірка
    try:
        still2 = register_client.table("register").select("id").eq("user_email", user_email).execute().data
    except Exception as e:
        log.warning("reject: recheck by email failed (%s): %s", user_email, e)
        still2 = None

    return not bool(still2)


@bp.post("/reg_user")
def reg_user():
    """
    approve: перенос із `register` → `contacts`; паролі одразу зберігаємо у вигляді bcrypt-хешу.
             auto_login=true → видати auth_tokens + expires_at.

    reject : додати email у `black_list` (user_email, user_name, user_phone, data) і видалити заявку з `register`.
    """
    data = request.json or {}
    action = (data.get("action") or "").lower()
    row_id = data.get("id")
    auto_login = bool(data.get("auto_login"))

    if action not in ("approve", "reject"):
        return jsonify({"error": "action must be approve | reject"}), 400
    if row_id is None:
        return jsonify({"error": "id is required"}), 400

    contacts = get_client_for_table("contacts")
    register = get_client_for_table("register")

    # ───────────────────────── reject ─────────────────────────
    if action == "reject":
        try:
            reg_row = register.table("register").select(
                "id,user_email,user_name,user_phone"
            ).eq("id", row_id).single().execute().data
        except Exception as e:
            log.error("reject: register read failed (id=%s): %s", row_id, e)
            return jsonify({"error": "register read failed"}), 500

        if not reg_row:
            return jsonify({"error": "register row not found"}), 404

        user_email = (reg_row.get("user_email") or "").strip().lower()
        user_name  = (reg_row.get("user_name")  or "").strip()
        user_phone = (reg_row.get("user_phone") or "").strip()

        bl = get_client_for_table("black_list")

        # перевірка, чи вже у блеклісті
        try:
            exists_bl = bl.table("black_list").select("user_id").eq("user_email", user_email).execute().data
        except Exception as e:
            log.warning("reject: blacklist check failed for %s: %s", user_email, e)
            exists_bl = None

        if not exists_bl:
            payload_main = {
                "user_email": user_email,
                "user_name":  user_name,
                "user_phone": user_phone,
                "data":       dt.datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00",
            }
            try:
                bl.table("black_list").insert(payload_main).execute()
            except Exception as e1:
                log.info("reject: insert with data failed, retrying without data: %s", e1)
                try:
                    payload_fallback = {k: v for k, v in payload_main.items() if k != "data"}
                    bl.table("black_list").insert(payload_fallback).execute()
                except Exception as e2:
                    log.error("reject: blacklist insert failed for %s: %s", user_email, e2)
                    return jsonify({"error": "blacklist insert failed"}), 500

        # гарантоване видалення заявки з register
        deleted = _delete_register_row(register, row_id, user_email)
        clear_cache("black_list")
        clear_cache("register")

        if not deleted:
            log.warning("reject: register row STILL PRESENT (id=%s, email=%s)", row_id, user_email)
            return jsonify({
                "status": "partial",
                "action": "reject",
                "warning": "blacklisted, but register row not deleted"
            }), 200

        return jsonify({"status": "ok", "action": "reject"}), 200

    # ───────────────────────── approve ─────────────────────────
    try:
        reg_row = register.table("register").select(
            "id,user_email,user_name,user_phone,pass_email"
        ).eq("id", row_id).single().execute().data
    except Exception as e:
        log.error("approve: register read failed (id=%s): %s", row_id, e)
        return jsonify({"error": "register read failed"}), 500

    if not reg_row:
        return jsonify({"error": "register row not found"}), 404

    user_email = (reg_row.get("user_email") or "").strip().lower()
    user_name  = (reg_row.get("user_name")  or "").strip()
    user_phone = (reg_row.get("user_phone") or "").strip()
    pass_raw   = (reg_row.get("pass_email") or "").strip()

    # дубль у contacts?
    try:
        exists = contacts.table("contacts").select("user_id").eq("user_email", user_email).execute().data
    except Exception as e:
        log.error("approve: contacts duplicate check failed: %s", e)
        exists = None
    if exists:
        # навіть при дублі намагаємось знести заявку
        _delete_register_row(register, row_id, user_email)
        clear_cache("register")
        return jsonify({"error": "duplicate in contacts"}), 409

    if pass_raw.startswith("$2"):
        pass_store = pass_raw
    else:
        pass_store = hash_password(pass_raw)

    payload = {
        "user_email":   user_email,
        "user_name":    user_name,
        "user_phone":   user_phone,
        "user_access":  "def",
        "extra_access": None,
        "pass_email":   pass_store,
    }

    if auto_login:
        payload["auth_tokens"] = secrets.token_urlsafe(32)
        payload["expires_at"]  = _exp_iso()

    try:
        ins = contacts.table("contacts").insert(payload).execute()
        # після успішного переносу — гарантовано видаляємо заявку
        _delete_register_row(register, row_id, user_email)
        clear_cache("contacts"); clear_cache("register")

        out = {
            "status": "ok",
            "action": "approve",
            "created_id": (ins.data and (ins.data[0].get("user_id") or ins.data[0].get("id")))
        }
        if auto_login:
            out["auth_tokens"] = payload["auth_tokens"]
            out["expires_at"]  = payload["expires_at"]
        return jsonify(out), 200
    except Exception as e:
        log.error("approve failed (id=%s, email=%s): %s", row_id, user_email, e)
        return jsonify({"error": "internal_error"}), 500
