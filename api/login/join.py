# api/login/join.py
import os
import re
import secrets
import datetime as dt
import logging
from typing import Optional, Tuple

from flask import Blueprint, request, jsonify, make_response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from api.coreapiserver import get_client_for_table, clear_cache
from services import tg_bot
from services.gmail import send_email, GmailConfigError

bp = Blueprint("login_join", __name__, url_prefix="/api/login")
bp_auth = Blueprint("login_auth", __name__, url_prefix="/api/auth")
bp_tg = Blueprint("login_tg", __name__, url_prefix="/api/tg")
bps = (bp_auth, bp_tg)

log = logging.getLogger("login.join")

# ── Cookie / TTL
COOKIE_NAME     = "edu_session"
AUTH_TTL_HOURS  = int(os.getenv("AUTH_TTL_HOURS", "168"))
EMAIL_RX        = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEBUG_ERRORS    = os.getenv("DEBUG_ERRORS", "0") == "1"
COOKIE_SECURE   = os.getenv("COOKIE_SECURE", "1") == "1"
LOGIN_DEBUG     = os.getenv("LOGIN_DEBUG", "0") == "1"
USE_TG_RECOVERY   = os.getenv("USE_TG_RECOVERY", "0") == "1"
USE_EMAIL_RECOVERY = os.getenv("USE_EMAIL_RECOVERY", "0") == "1"
RECOVERY_CONFIG_ID = int(os.getenv("RECOVERY_CONFIG_ID", "5"))
RESET_TOKEN_TTL_MIN   = int(os.getenv("RESET_TOKEN_TTL_MINUTES", "10"))
TG_LINK_TOKEN_TTL_HRS = int(os.getenv("TG_LINK_TOKEN_TTL_HOURS", "10"))
PUBLIC_APP_URL        = os.getenv("PUBLIC_APP_URL") or os.getenv("APP_BASE_URL")
RECOVERY_CHAT_FIELD   = "recovery_tg_id"
RESET_CODE_FIELD      = "recovery_code"
RESET_TIME_FIELD      = "password_resets_time"

FORGOT_GENERIC_MSG     = "Якщо акаунт існує — ми надіслали інструкції з відновлення."
FORGOT_TG_MSG          = "Якщо акаунт існує — ми надіслали інструкції у Telegram."
FORGOT_EMAIL_MSG       = "Якщо акаунт існує — ми надіслали інструкції на email."
FORGOT_EMAIL_DISABLED  = "Email-відновлення зараз недоступне. Зверніться до адміністратора."
FORGOT_UNAVAILABLE_MSG = "Скидання паролю зараз недоступне."
RESET_LINK_INVALID_MSG = "Посилання недійсне."
RESET_LINK_EXPIRED_MSG = "Термін дії посилання минув."

TG_SUCCESS_TEXT = "✅ Дякуємо! Ви успішно підключили Telegram-бота."
TG_NO_PHONE_TEXT = "ℹ️ У вашому акаунті не вказано номер телефону."
TG_MISMATCH_TEXT = "⚠️ Номер телефону не збігається."
TG_BAD_TOKEN_TEXT = "Посилання недійсне."

try:
    import bcrypt
except Exception:
    bcrypt = None

def _is_bcrypt_hash(stored: str) -> bool:
    return bool(stored and stored.strip().startswith("$2"))

def hash_password(raw: str) -> str:
    if not raw: raise ValueError("Пароль порожній")
    if not bcrypt: return raw
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _check_pwd(p: str, stored: str) -> bool:
    if not stored: return False
    s = stored.strip()
    if _is_bcrypt_hash(s) and bcrypt:
        try: return bcrypt.checkpw(p.encode("utf-8"), s.encode("utf-8"))
        except: return False
    return p == s

def _now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00"

def _utcnow():
    return dt.datetime.now(dt.timezone.utc)

def _parse_toggle(value) -> Optional[bool]:
    if value is None: return None
    if isinstance(value, bool): return value
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "on"}

def _get_recovery_toggles() -> Tuple[bool, bool]:
    allow_tg = USE_TG_RECOVERY
    allow_email = USE_EMAIL_RECOVERY
    try:
        base = get_client_for_table("uni_base")
        row = base.table("uni_base").select("jsonb,jsonb2").eq("id", RECOVERY_CONFIG_ID).single().execute().data
        if row:
            if row.get("jsonb") is not None: allow_tg = _parse_toggle(row.get("jsonb"))
            if row.get("jsonb2") is not None: allow_email = _parse_toggle(row.get("jsonb2"))
    except: pass
    return allow_tg, allow_email

def _parse_timestamp(value: Optional[str]) -> Optional[dt.datetime]:
    if not value: return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except: return None

def _exp_iso():
    return (dt.datetime.utcnow() + dt.timedelta(hours=AUTH_TTL_HOURS)).replace(microsecond=0).isoformat() + "+00:00"

def _set_cookie(resp, token: str):
    resp.set_cookie(COOKIE_NAME, token, max_age=AUTH_TTL_HOURS * 3600, path="/", httponly=True, secure=COOKIE_SECURE, samesite="Lax")
    return resp

def _payload_from_row(row: dict):
    payload = {
        "user_id":      row.get("user_id"),
        "user_name":    row.get("user_name"),
        "user_phone":   row.get("user_phone"),
        "user_access":  row.get("user_access"),
    }
    payload["need_tg_setup"] = not bool(row.get(RECOVERY_CHAT_FIELD))
    return payload

def _mask_email(e: str) -> str:
    if not e: return "-"
    m = re.match(r"^([^@]{0,3})[^@]*(@.*)$", e)
    return (m.group(1) + "***" + m.group(2)) if m else e[:2] + "***"

def _fail_invalid():
    return jsonify(error="invalid_credentials", message="Невірний email або пароль"), 401

def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone: return None
    digits = re.sub(r"\D", "", phone)
    if not digits: return None
    if digits.startswith("380") and len(digits) >= 12: return "+380" + digits[-9:]
    if digits.startswith("0") and len(digits) >= 10: return "+380" + digits[-9:]
    if len(digits) == 9: return "+380" + digits
    return None

def _get_link_serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("TG_LINK_SECRET") or os.getenv("SECRET_KEY")
    if not secret: raise RuntimeError("TG_LINK_SECRET required")
    return URLSafeTimedSerializer(secret_key=secret, salt="eduvision-tg-link")

def _sign_user_token(user_id: int) -> str:
    return _get_link_serializer().dumps({"user_id": user_id})

def _unsign_user_token(token: str) -> str:
    # ID is string in new DB
    data = _get_link_serializer().loads(token, max_age=TG_LINK_TOKEN_TTL_HRS * 3600)
    return str(data.get("user_id"))

def _issue_session(contacts_client, user_id) -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    exp   = _exp_iso()
    # Also updating last_login
    contacts_client.table("contacts").update({
        "auth_tokens": token,
        "expires_at":  exp,
        "last_login":  _now_iso()
    }).eq("user_id", user_id).execute()
    return token, exp

def _build_reset_link(token: str) -> str:
    base = (PUBLIC_APP_URL or request.host_url).rstrip("/") + "/"
    return f"{base}#reset?token={token}"

def _store_reset_code(user_id) -> Tuple[str, str]:
    contacts = get_client_for_table("contacts")
    token = secrets.token_urlsafe(32)
    issued = _now_iso()
    contacts.table("contacts").update({
        RESET_CODE_FIELD: token,
        RESET_TIME_FIELD: issued,
    }).eq("user_id", user_id).execute()
    clear_cache("contacts")
    return token, issued

def _resolve_user_by_token(token: str) -> Optional[dict]:
    try:
        return get_client_for_table("contacts").table("contacts").select(
            "user_id,user_name,user_phone,user_email,user_access,{tg}".format(tg=RECOVERY_CHAT_FIELD)
        ).eq("auth_tokens", token).gt("expires_at", _now_iso()).single().execute().data
    except: return None

def _get_user_for_request() -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    return _resolve_user_by_token(token) if token else None

def _send_tg_reset(chat_id: str, link: str) -> None:
    tg_bot.send_message_httpx(int(chat_id), f"🔒 Відновлення доступу:\n{link}")

def _send_email_reset(email: str, link: str, subject: str) -> None:
    send_email(email, subject, f"<a href='{link}'>Скинути пароль</a>")

def _send_tg_link_email(email: str, bot_link: str) -> None:
    send_email(email, "Telegram Bot", f"<a href='{bot_link}'>Підключити бота</a>")

def _get_reset_row(token: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        row = get_client_for_table("contacts").table("contacts").select(
            "user_id,user_email,user_name,{code},{ts}".format(code=RESET_CODE_FIELD, ts=RESET_TIME_FIELD)
        ).eq(RESET_CODE_FIELD, token).single().execute().data
    except: return None, "invalid"

    if not row or not row.get(RESET_CODE_FIELD): return None, "invalid"
    issued = _parse_timestamp(row.get(RESET_TIME_FIELD))
    if not issued: return None, "invalid"
    if (issued + dt.timedelta(minutes=RESET_TOKEN_TTL_MIN)) <= _utcnow(): return None, "expired"
    return row, None

def _clear_reset_code(user_id) -> None:
    try:
        get_client_for_table("contacts").table("contacts").update({
            RESET_CODE_FIELD: None, RESET_TIME_FIELD: None
        }).eq("user_id", user_id).execute()
    except: pass

@bp.post("/register")
def register_user():
    b = request.get_json(silent=True) or {}
    email, name = (b.get("user_email") or "").strip().lower(), (b.get("user_name") or "").strip()
    phone, pwd = (b.get("user_phone") or "").strip(), (b.get("pass_email") or "")

    if not (email and name and phone and pwd): return jsonify(error="val_err", message="Заповніть всі поля"), 400
    if not EMAIL_RX.match(email): return jsonify(error="val_err", message="Невірний email"), 400
    if len(pwd) < 6: return jsonify(error="val_err", message="Пароль короткий"), 400

    contacts = get_client_for_table("contacts")
    register = get_client_for_table("register")

    try:
        if contacts.table("contacts").select("user_id").eq("user_email", email).execute().data:
            return jsonify(error="already_registered", message="Користувач вже існує"), 409
        if register.table("register").select("$id").eq("user_email", email).execute().data:
            return jsonify(message="Заявка вже подана"), 200

        res = register.table("register").insert({
            "user_email": email, "user_name": name, "user_phone": phone, "pass_email": hash_password(pwd)
        }).execute()

        if not getattr(res, "data", None): return jsonify(error="server_error"), 500
        return jsonify(message="Заявку прийнято"), 200
    except Exception as e:
        log.error(f"register fail: {e}")
        return jsonify(error="server_error"), 500

@bp.post("/join")
def join():
    b = request.get_json(silent=True) or {}
    email, pwd = (b.get("email") or b.get("user_email") or "").strip().lower(), (b.get("password") or b.get("pass_email") or "")
    if not email or not pwd: return _fail_invalid()

    contacts = get_client_for_table("contacts")
    try:
        # Прибрано extra_access, бо його немає в базі
        row = contacts.table("contacts").select(
            "user_id,user_email,user_name,user_phone,user_access,pass_email,is_active,{tg}".format(tg=RECOVERY_CHAT_FIELD)
        ).eq("user_email", email).single().execute().data
    except: row = None

    if not row: return _fail_invalid()
    
    # Перевірка isActive
    if row.get("is_active") is False:
        return jsonify(error="blocked", message="Акаунт заблоковано"), 403

    if not _check_pwd(pwd, row.get("pass_email")): return _fail_invalid()

    # Оновлення токена та last_login
    try:
        token, _ = _issue_session(contacts, row["user_id"])
    except Exception as e:
        log.error(f"auth token fail: {e}")
        return jsonify(error="server_error"), 500

    payload = _payload_from_row(row)
    resp = make_response(jsonify(ok=True, need_tg_setup=payload["need_tg_setup"]))
    return _set_cookie(resp, token)

@bp.get("/me")
def me():
    token = request.cookies.get(COOKIE_NAME)
    if not token: return jsonify(error="unauthorized"), 401
    row = _resolve_user_by_token(token)
    if not row: return jsonify(error="unauthorized"), 401
    return jsonify(ok=True, user=_payload_from_row(row))

@bp.post("/logout")
def logout():
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            get_client_for_table("contacts").table("contacts").update({"auth_tokens": None, "expires_at": None}).eq("auth_tokens", token).execute()
        except: pass
    resp = make_response(jsonify(ok=True))
    resp.set_cookie(COOKIE_NAME, "", max_age=0, path="/")
    return resp

@bp.post("/forgot")
def forgot_password():
    email = (request.get_json(silent=True) or {}).get("email", "").strip().lower()
    if not EMAIL_RX.match(email): return jsonify(message=FORGOT_GENERIC_MSG), 200

    contacts = get_client_for_table("contacts")
    try:
        row = contacts.table("contacts").select("user_id,user_email,user_name,{tg}".format(tg=RECOVERY_CHAT_FIELD)).eq("user_email", email).single().execute().data
    except: row = None

    if not row: return jsonify(message=FORGOT_GENERIC_MSG), 200

    allow_tg, allow_email = _get_recovery_toggles()
    recovery_chat = row.get(RECOVERY_CHAT_FIELD)
    
    if allow_tg and recovery_chat:
        token, _ = _store_reset_code(row["user_id"])
        _send_tg_reset(recovery_chat, _build_reset_link(token))
        return jsonify(message=FORGOT_TG_MSG)
    elif allow_email:
        token, _ = _store_reset_code(row["user_id"])
        try:
            _send_email_reset(email, _build_reset_link(token), "Скидання паролю")
            return jsonify(message=FORGOT_EMAIL_MSG)
        except Exception as e:
            log.error(f"Email fail: {e}")
            return jsonify(message=FORGOT_EMAIL_DISABLED), 200
    
    return jsonify(message=FORGOT_UNAVAILABLE_MSG), 200

@bp.post("/reset")
def reset_password():
    data = request.get_json(silent=True) or {}
    token, pwd = data.get("token"), data.get("new_password")
    if not token or len(pwd or "") < 6: return jsonify(error="val_err"), 400

    row, reason = _get_reset_row(token)
    if not row: return jsonify(error="invalid_token", message=RESET_LINK_EXPIRED_MSG if reason=="expired" else RESET_LINK_INVALID_MSG), 400

    try:
        get_client_for_table("contacts").table("contacts").update({"pass_email": hash_password(pwd)}).eq("user_id", row["user_id"]).execute()
        _clear_reset_code(row["user_id"])
        token_val, _ = _issue_session(get_client_for_table("contacts"), row["user_id"])
        resp = make_response(jsonify(ok=True))
        return _set_cookie(resp, token_val)
    except Exception as e:
        log.error(f"Reset fail: {e}")
        return jsonify(error="server_error"), 500

@bp_auth.post("/send_tg_link")
def send_tg_link():
    user = _get_user_for_request()
    if not user: return jsonify(error="unauthorized"), 401
    try:
        link = f"https://t.me/{tg_bot.get_bot_username()}?start={_sign_user_token(user['user_id']).replace('.', '-')}"
        _send_tg_link_email(user.get("user_email"), link)
        return jsonify(ok=True)
    except Exception as e:
        log.error(f"TG Link fail: {e}")
        return jsonify(ok=True, delivery="manual", message="Збій пошти, зверніться до адміна")

@bp_tg.post("/link_recovery")
def link_recovery():
    data = request.get_json(silent=True) or {}
    try:
        user_id = _unsign_user_token(data.get("user_token"))
    except: return jsonify(error="invalid_token", bot_text=TG_BAD_TOKEN_TEXT), 400

    contacts = get_client_for_table("contacts")
    row = contacts.table("contacts").select("user_id,user_phone").eq("user_id", user_id).single().execute().data
    if not row: return jsonify(error="not_found"), 404

    db_ph, tg_ph = _normalize_phone(row.get("user_phone")), _normalize_phone(data.get("phone"))
    if not db_ph: return jsonify(status="missing_phone", bot_text=TG_NO_PHONE_TEXT)
    if db_ph != tg_ph: return jsonify(status="phone_mismatch", bot_text=TG_MISMATCH_TEXT)

    contacts.table("contacts").update({RECOVERY_CHAT_FIELD: str(data.get("chat_id")), "user_tg_id": str(data.get("chat_id"))}).eq("user_id", user_id).execute()
    return jsonify(status="ok", bot_text=TG_SUCCESS_TEXT)
