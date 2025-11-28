# api/login/join.py
import os
import re
import secrets
import datetime as dt
import logging
from typing import Optional, Tuple, List

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

# ─────────────────────────────────────────────────────────────
# КОНФІГУРАЦІЯ
# ─────────────────────────────────────────────────────────────
COOKIE_NAME     = "edu_session"
AUTH_TTL_HOURS  = int(os.getenv("AUTH_TTL_HOURS", "168"))  # 7 днів
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

# Список таблиць для авторизації (пріоритет зверху вниз)
# (назва_таблиці, дефолтна_роль, поле_ролі_в_бд)
AUTH_TABLES = [
    ("contacts", "teacher", "user_access"),  # Вчителі/Адміни
    ("parents",  "parent",  None),           # Батьки
    ("student", "student", None)            # Учні
]

# Тексти повідомлень (зберігаємо ваші оригінальні)
FORGOT_GENERIC_MSG     = "Якщо акаунт існує — ми надіслали інструкції з відновлення."
FORGOT_TG_MSG          = "Якщо акаунт існує — ми надіслали інструкції у Telegram."
FORGOT_EMAIL_MSG       = "Якщо акаунт існує — ми надіслали інструкції на email."
FORGOT_EMAIL_DISABLED  = (
    "Email-відновлення зараз недоступне, бо сервіс надсилання листів не налаштований."
    " Зверніться до адміністратора або скористайтесь Telegram-ботом."
)
FORGOT_UNAVAILABLE_MSG = "Скидання паролю зараз недоступне. Зверніться до адміністратора вашого навчального центру."
RESET_LINK_INVALID_MSG = "Посилання для скидання пароля недійсне. Натисніть «Забув пароль» і запросіть нове."
RESET_LINK_EXPIRED_MSG = "Термін дії посилання на скидання пароля минув. Спробуйте ще раз запросити відновлення."

TG_SUCCESS_TEXT = (
    "✅ Дякуємо!\n"
    "Ваш номер телефону збігається з номером у системі EduVision.\n\n"
    "Ви успішно підключили Telegram-бота Helen Doron English до вашого акаунта.\n"
    "Тепер ви можете відновлювати пароль та отримувати важливі повідомлення через цей бот.\n\n"
    "Поверніться в EduVision, оновіть сторінку та зайдіть у свій акаунт."
)
TG_NO_PHONE_TEXT = (
    "ℹ️ У вашому акаунті EduVision не вказано номер телефону.\n\n"
    "Щоб підключити Telegram-бота, адміністратор має додати ваш актуальний номер телефона в систему.\n"
    "Будь ласка, зверніться до адміністратора вашого навчального центру і попросіть додати ваш номер в EduVision."
)
TG_MISMATCH_TEXT = (
    "⚠️ Номер телефону не збігається\n\n"
    "Номер із Telegram не відповідає номеру, збереженому у вашому акаунті EduVision.\n\n"
    "Можливі причини:\n• ви змінили номер і він ще не оновлений у системі;\n• ви намагаєтесь підключити чужий акаунт.\n\n"
    "Будь ласка, зверніться до адміністратора навчального центру, "
    "повідомте ваш актуальний номер і попросіть оновити його в EduVision. Після оновлення повторіть спробу."
)
TG_BAD_TOKEN_TEXT = (
    "Посилання недійсне або термін дії минув. \n"
    "Поверніться на сайт EduVision і натисніть «Надіслати лист» ще раз."
)

# ─────────────────────────────────────────────────────────────
# УТИЛІТИ
# ─────────────────────────────────────────────────────────────
try:
    import bcrypt
except Exception:  # pragma: no cover
    bcrypt = None

def _is_bcrypt_hash(stored: str) -> bool:
    return bool(stored and stored.strip().startswith("$2"))

def hash_password(raw: str) -> str:
    if not raw:
        raise ValueError("Пароль не може бути порожнім")
    if not bcrypt:
        raise RuntimeError("bcrypt не встановлений. Додайте його до requirements.txt")
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _check_pwd(p: str, stored: str) -> bool:
    if not stored:
        return False
    s = stored.strip()
    if _is_bcrypt_hash(s):
        try:
            return bool(bcrypt and bcrypt.checkpw(p.encode("utf-8"), s.encode("utf-8")))
        except Exception:
            return False
    if s.startswith("pbkdf2:"):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(s, p)
        except Exception:
            return False
    return p == s

def _now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00"

def _utcnow():
    return dt.datetime.now(dt.timezone.utc)

def _parse_toggle(value) -> Optional[bool]:
    """Повертає булеве значення з різних форматів (1, true, on)."""
    if value is None: return None
    if isinstance(value, bool): return value
    try:
        if isinstance(value, (int, float)): return bool(int(value))
    except (TypeError, ValueError): pass
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}: return True
    if text in {"0", "false", "f", "no", "n", "off"}: return False
    return None

def _get_recovery_toggles() -> Tuple[bool, bool]:
    """Повертає (allow_tg, allow_email) з урахуванням налаштування в uni_base."""
    allow_tg = USE_TG_RECOVERY
    allow_email = USE_EMAIL_RECOVERY

    try:
        base = get_client_for_table("uni_base")
        row = base.table("uni_base").select("jsonb,jsonb2").eq("id", RECOVERY_CONFIG_ID) \
            .single().execute().data
    except Exception as exc:
        log.debug("recovery toggles fallback to env: %s", exc)
        row = None

    if row:
        tg_flag = _parse_toggle(row.get("jsonb"))
        email_flag = _parse_toggle(row.get("jsonb2"))
        if tg_flag is not None:
            allow_tg = tg_flag
        if email_flag is not None:
            allow_email = email_flag

    return allow_tg, allow_email

def _parse_timestamp(value: Optional[str]) -> Optional[dt.datetime]:
    if not value: return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError: return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)

def _exp_iso():
    return (dt.datetime.utcnow() + dt.timedelta(hours=AUTH_TTL_HOURS)) \
            .replace(microsecond=0).isoformat() + "+00:00"

def _set_cookie(resp, token: str):
    resp.set_cookie(
        COOKIE_NAME, token,
        max_age=AUTH_TTL_HOURS * 3600, path="/",
        httponly=True, secure=COOKIE_SECURE, samesite="Lax"
    )
    return resp

def _payload_from_row(row: dict, table_name: str = "contacts"):
    """Формує відповідь для фронтенду, адаптуючи поля залежно від таблиці."""
    role = _get_user_role(row, table_name)
    payload = {
        "user_id":      row.get("user_id"),
        "user_name":    row.get("user_name") or row.get("full_name"), # fallback для parents/students
        "user_phone":   row.get("user_phone") or row.get("phone"),
        "user_email":   row.get("user_email") or row.get("email"),
        "user_access":  role,
        "role":         role,
        "table":        table_name,
        "extra_access": row.get("extra_access"),
    }
    payload["need_tg_setup"] = _need_tg_setup(row)
    return payload

def _mask_email(e: str) -> str:
    if not e: return "-"
    e = e.strip().lower()
    m = re.match(r"^([^@]{0,3})[^@]*(@.*)$", e)
    return (m.group(1) + "***" + m.group(2)) if m else e[:2] + "***"

def _fail_invalid():
    return jsonify(error="invalid_credentials", message="Невірний email або пароль"), 401

def _need_tg_setup(row: dict) -> bool:
    recovery = _get_recovery_chat(row)
    return not bool(recovery)

def _get_recovery_chat(row: dict) -> Optional[str]:
    return row.get(RECOVERY_CHAT_FIELD) or row.get("recovery_pass_tg")

def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone: return None
    digits = re.sub(r"\D", "", phone)
    if not digits: return None
    if digits.startswith("380") and len(digits) >= 12: core = digits[-9:]
    elif digits.startswith("0") and len(digits) >= 10: core = digits[-9:]
    elif len(digits) == 9: core = digits
    else: return None
    return "+380" + core

def _get_link_serializer() -> URLSafeTimedSerializer:
    secret = None
    for key in ("TG_LINK_SECRET", "SECRET_KEY", "HDD", "HDD2"):
        value = os.getenv(key)
        if value:
            secret = value
            break
    if not secret:
        raise RuntimeError("No SECRET_KEY for TG link")
    return URLSafeTimedSerializer(secret_key=secret, salt="eduvision-tg-link")

# ОНОВЛЕНО: додано table
def _sign_user_token(user_id: int, table: str = "contacts") -> str:
    serializer = _get_link_serializer()
    return serializer.dumps({"user_id": user_id, "table": table})

# ОНОВЛЕНО: повертає ID і table
def _unsign_user_token(token: str) -> Tuple[int, str]:
    serializer = _get_link_serializer()
    data = serializer.loads(token, max_age=TG_LINK_TOKEN_TTL_HRS * 3600)
    return int(data.get("user_id")), data.get("table", "contacts")

def _issue_session(client, table: str, user_id: int) -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    exp   = _exp_iso()
    client.table(table).update({
        "auth_tokens": token,
        "expires_at":  exp
    }).eq("user_id", user_id).execute()
    return token, exp

def _build_reset_link(token: str) -> str:
    base = (PUBLIC_APP_URL or request.host_url).rstrip("/")
    return f"{base}/#reset?token={token}"

def _store_reset_code(client, table: str, user_id: int) -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    issued = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    client.table(table).update({
        RESET_CODE_FIELD: token,
        RESET_TIME_FIELD: issued,
    }).eq("user_id", user_id).execute()
    clear_cache(table) # Очищаємо кеш конкретної таблиці
    return token, issued

def _send_tg_reset(chat_id: str, link: str) -> None:
    tg_bot.send_message_httpx(int(chat_id), (
        "🔒 Відновлення доступу до EduVision\n"
        "Натисніть на посилання, щоб задати новий пароль:\n"
        f"{link}"
    ))

def _send_email_reset(email: str, link: str, subject: str) -> None:
    html = (
        "<p>Щоб відновити доступ до EduVision, перейдіть за посиланням і задайте новий пароль:</p>"
        f"<p><a href=\"{link}\">Відкрити форму скидання паролю</a></p>"
        "<p>Посилання дійсне обмежений час.</p>"
    )
    send_email(email, subject, html)

def _send_tg_link_email(email: str, bot_link: str) -> None:
    html = (
        "<p>Щоб захистити ваш акаунт EduVision, підключіть Telegram-бота.</p>"
        f"<p><a href=\"{bot_link}\">👉 Відкрити бота</a></p>"
        "<p>Натисніть Start у боті та поділіться номером телефону.</p>"
    )
    send_email(email, "Підключення Telegram-бота", html)

def _clear_reset_code(client, table: str, user_id: int) -> None:
    try:
        client.table(table).update({
            RESET_CODE_FIELD: None,
            RESET_TIME_FIELD: None,
        }).eq("user_id", user_id).execute()
    except Exception as exc:
        log.warning("Не вдалося очистити код відновлення user_id=%s: %s", user_id, exc)
    clear_cache(table)

# ─────────────────────────────────────────────────────────────
# NEW: MULTI-TABLE HELPERS
# ─────────────────────────────────────────────────────────────

def _find_user_in_tables(field: str, value: str) -> Tuple[Optional[dict], Optional[str]]:
    """Шукає користувача у contacts, parents, students."""
    if not value: return None, None
    for table, _, _ in AUTH_TABLES:
        try:
            client = get_client_for_table(table)
            # Шукаємо потрібні поля. Для оптимізації можна вибирати тільки їх, але select("*") надійніше
            row = client.table(table).select("*").eq(field, value).single().execute().data
            if row:
                return row, table
        except Exception:
            continue
    return None, None

def _resolve_user_by_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
    """Пошук юзера по токену у всіх дозволених таблицях."""
    if not token: return None, None
    
    # Спочатку шукаємо в contacts (найчастіший кейс)
    # Але для коректності треба пробігтись по всіх або знати таблицю заздалегідь (тут ми не знаємо)
    row, table = _find_user_in_tables("auth_tokens", token)
    
    if row:
        exp_str = row.get("expires_at")
        if exp_str:
            exp_at = _parse_timestamp(exp_str)
            if exp_at and exp_at > _utcnow():
                return row, table
    return None, None

def _get_user_role(row: dict, table: str) -> str:
    """Визначає роль користувача на основі таблиці."""
    for t_name, def_role, role_col in AUTH_TABLES:
        if t_name == table:
            if role_col and row.get(role_col):
                return row.get(role_col)
            return def_role
    return "guest"

# Helper for other modules (retains backward compatibility)
def _get_user_for_request() -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    row, table = _resolve_user_by_token(token)
    if row:
        # Inject metadata for generic API usage
        row["user_access"] = _get_user_role(row, table)
        row["_table"] = table 
    return row

def _get_reset_row(token: str) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    """Повертає (row, reason, table_name)."""
    row, table = _find_user_in_tables(RESET_CODE_FIELD, token)
    
    if not row:
        return None, "invalid", None

    issued = _parse_timestamp(row.get(RESET_TIME_FIELD))
    if not issued:
        return None, "invalid", None

    expires_at = issued + dt.timedelta(minutes=RESET_TOKEN_TTL_MIN)
    if expires_at <= _utcnow():
        return None, "expired", None

    return row, None, table

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@bp.post("/register")
def register_user():
    # Цей метод стосується ТІЛЬКИ співробітників (contacts), тому логіку не змінюємо
    b = request.get_json(silent=True) or {}
    email = (b.get("user_email") or "").strip().lower()
    name  = (b.get("user_name")  or "").strip()
    phone = (b.get("user_phone") or "").strip()
    pwd   = (b.get("pass_email") or "")

    if not (email and name and phone and pwd):
        return jsonify(error="validation_error", message="Заповніть усі поля"), 400
    if not EMAIL_RX.match(email):
        return jsonify(error="validation_error", message="Невірний email"), 400
    if len(pwd) < 6:
        return jsonify(error="validation_error", message="Пароль має бути від 6 символів"), 400

    contacts = get_client_for_table("contacts")
    register = get_client_for_table("register")

    try:
        if contacts.table("contacts").select("user_id").eq("user_email", email).execute().data:
            return jsonify(error="already_registered", message="Користувач уже існує."), 409

        if register.table("register").select("id").eq("user_email", email).execute().data:
            return jsonify(message="Заявку вже подано. Очікуйте підтвердження."), 200

        register.table("register").insert({
            "user_email": email,
            "user_name":  name,
            "user_phone": phone,
            "pass_email": hash_password(pwd),
        }).execute()

        return jsonify(message="Заявку прийнято. Очікуйте підтвердження адміністратора."), 200

    except Exception as e:
        body = {"error": "server_error", "message": "Не вдалося створити заявку."}
        if DEBUG_ERRORS:
            body["detail"] = str(e)
        log.error("register failed for %s: %s", _mask_email(email), e)
        return jsonify(body), 500

@bp.post("/join")
def join():
    b = request.get_json(silent=True) or {}
    email = (b.get("email") or b.get("user_email") or "").strip().lower()
    pwd   = (b.get("password") or b.get("pass_email") or "")

    if not email or not pwd:
        return _fail_invalid()

    # ОНОВЛЕНО: Пошук по всіх таблицях
    row, table = _find_user_in_tables("user_email", email)

    if not row:
        log.info("login fail (no user): %s", _mask_email(email))
        return _fail_invalid()

    stored = row.get("pass_email") or ""
    if not _check_pwd(pwd, stored):
        log.info("login fail (bad pwd): %s", _mask_email(email))
        return _fail_invalid()

    client = get_client_for_table(table)

    # Оновлення хешу до bcrypt, якщо старий (тільки якщо є права запису)
    if not _is_bcrypt_hash(stored):
        try:
            new_hash = hash_password(pwd)
            client.table(table).update({"pass_email": new_hash}).eq("user_id", row["user_id"]).execute()
            row["pass_email"] = new_hash
        except Exception as exc:
            log.warning("Не вдалося оновити пароль до bcrypt: %s", exc)

    try:
        token, _ = _issue_session(client, table, row["user_id"])
    except Exception as e:
        body = {"error":"server_error", "message":"Не вдалося видати сесію"}
        if DEBUG_ERRORS: body["detail"] = str(e)
        log.error("set auth token failed: %s", e)
        return jsonify(body), 500

    # ОНОВЛЕНО: payload_from_row з урахуванням таблиці
    payload = _payload_from_row(row, table)
    resp = make_response(jsonify(ok=True, need_tg_setup=payload["need_tg_setup"]))
    return _set_cookie(resp, token)

@bp.get("/me")
def me():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify(error="unauthorized"), 401

    row, table = _resolve_user_by_token(token)

    if not row:
        return jsonify(error="unauthorized"), 401

    payload = _payload_from_row(row, table)
    return jsonify(ok=True, **payload, user=payload)

@bp.post("/logout")
def logout():
    token = request.cookies.get(COOKIE_NAME)
    if token:
        row, table = _resolve_user_by_token(token)
        if row:
            try:
                client = get_client_for_table(table)
                client.table(table).update({"auth_tokens": None, "expires_at": None}) \
                        .eq("auth_tokens", token).execute()
            except Exception as e:
                log.info("logout token clear failed: %s", e)
    resp = make_response(jsonify(ok=True))
    resp.set_cookie(COOKIE_NAME, "", path="/", max_age=0,
                    httponly=True, secure=COOKIE_SECURE, samesite="Lax")
    return resp

@bp.post("/forgot")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not EMAIL_RX.match(email):
        return jsonify(message=FORGOT_GENERIC_MSG), 200

    # ОНОВЛЕНО: Пошук по всіх таблицях
    row, table = _find_user_in_tables("user_email", email)

    if not row:
        return jsonify(message=FORGOT_GENERIC_MSG), 200

    # Повертаємо логіку перевірки toggles з бази
    allow_tg, allow_email = _get_recovery_toggles()

    recovery_chat = _get_recovery_chat(row)
    has_tg = bool(recovery_chat)
    method = None
    if allow_tg and has_tg:
        method = "tg"
    elif allow_email:
        method = "email"

    if not method:
        if allow_tg and not has_tg and not allow_email:
            msg = (
                "Скидання паролю через Telegram стане доступним після підключення бота. "
                "Будь ласка, увійдіть у свій акаунт, натисніть «Надіслати лист» і виконайте інструкції "
                "або зверніться до адміністратора вашого навчального центру."
            )
        else:
            msg = FORGOT_UNAVAILABLE_MSG
        return jsonify(message=msg), 200

    client = get_client_for_table(table)
    try:
        token, _ = _store_reset_code(client, table, row["user_id"])
    except Exception as e:
        log.error("Store reset code failed: %s", e)
        return jsonify(error="server_error"), 500

    link = _build_reset_link(token)

    try:
        if method == "tg":
            _send_tg_reset(recovery_chat, link)
            msg = FORGOT_TG_MSG
        else:
            _send_email_reset(email, link, "Скидання паролю EduVision")
            msg = FORGOT_EMAIL_MSG
    except GmailConfigError as exc:
        log.warning("email recovery disabled for %s: %s", _mask_email(email), exc)
        return jsonify(message=FORGOT_EMAIL_DISABLED), 200
    except Exception as exc:
        log.error("reset delivery failed for %s: %s", _mask_email(email), exc)
        return jsonify(error="delivery_failed", message="Не вдалося надіслати інструкції."), 500

    body = {"message": msg}
    if LOGIN_DEBUG:
        body["debug_link"] = link
    return jsonify(body)

@bp.post("/reset")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify(error="validation_error", message="Пароль має бути від 6 символів"), 400
    if not token:
        return jsonify(error="validation_error", message="Некоректний токен"), 400

    # ОНОВЛЕНО: отримання row разом з table
    row, reason, table = _get_reset_row(token)
    
    if not row:
        message = RESET_LINK_EXPIRED_MSG if reason == "expired" else RESET_LINK_INVALID_MSG
        return jsonify(error="invalid_token", message=message), 400

    client = get_client_for_table(table)
    pass_hash = hash_password(new_password)

    try:
        client.table(table).update({"pass_email": pass_hash}).eq("user_id", row["user_id"]).execute()
    except Exception as exc:
        log.error("reset password update failed: %s", exc)
        return jsonify(error="server_error", message="Не вдалося оновити пароль"), 500

    _clear_reset_code(client, table, row["user_id"])

    try:
        token_value, _ = _issue_session(client, table, row["user_id"])
    except Exception:
        token_value = None

    resp = make_response(jsonify(ok=True))
    if token_value:
        _set_cookie(resp, token_value)
    return resp

@bp_auth.post("/send_tg_link")
def send_tg_link():
    user = _get_user_for_request()
    if not user:
        return jsonify(error="unauthorized"), 401

    try:
        bot_username = tg_bot.get_bot_username()
    except Exception as exc:
        log.error("bot username not available: %s", exc)
        return jsonify(error="config_error", message="Telegram-бот не налаштований"), 500

    try:
        # ОНОВЛЕНО: додаємо table в токен
        table = user.get("_table", "contacts")
        token = _sign_user_token(user["user_id"], table=table)
    except RuntimeError as exc:
        log.error("sign token misconfigured: %s", exc)
        return jsonify(error="config_error", message=str(exc)), 500
    except Exception as exc:
        log.error("sign token failed: %s", exc)
        return jsonify(error="server_error", message="Не вдалося сформувати посилання"), 500

    safe_token = token.replace(".", "-")
    link = f"https://t.me/{bot_username}?start={safe_token}"

    try:
        # Для students/parents може не бути email або він пустий
        user_email = user.get("user_email")
        if not user_email:
             return jsonify(ok=True, bot_link=link, delivery="manual", message="Пошти немає. Скористайтесь посиланням вручну.")
             
        _send_tg_link_email(user_email, link)
    except GmailConfigError as exc:
        log.warning("gmail config missing: %s", exc)
        return jsonify(
            ok=True,
            bot_link=link,
            delivery="manual",
            message="Email-сервіс не налаштований. Скопіюйте посилання та відкрийте Telegram вручну.",
        )
    except Exception as exc:
        log.error("send tg link email failed: %s", exc)
        return jsonify(error="delivery_failed", message="Не вдалося надіслати лист"), 500

    return jsonify(ok=True)

@bp_tg.post("/link_recovery")
def link_recovery():
    data = request.get_json(silent=True) or {}
    token = (data.get("user_token") or "").strip()
    chat_id = data.get("chat_id")
    phone = data.get("phone") or ""

    if not (token and chat_id and phone):
        return jsonify(error="validation_error", bot_text="Недостатньо даних."), 400

    try:
        # ОНОВЛЕНО: розшифровуємо table
        user_id, table = _unsign_user_token(token)
    except (BadSignature, SignatureExpired) as exc:
        log.warning("link_recovery invalid token: %s", exc)
        return jsonify(error="invalid_token", bot_text=TG_BAD_TOKEN_TEXT), 400

    client = get_client_for_table(table)
    try:
        # Адаптуємо запит під різні таблиці (у student/parents телефон може називатися phone, а не user_phone)
        # Але в AUTH_TABLES ми не маємо мапінгу колонок.
        # Спробуємо універсальний select, _normalize_phone розбереться
        row = client.table(table).select("*").eq("user_id", user_id).single().execute().data
    except Exception as exc:
        log.error("link_recovery user lookup failed: %s", exc)
        row = None

    if not row:
        return jsonify(error="not_found", bot_text="Акаунт не знайдено."), 404

    # Отримуємо телефон з різних можливих полів
    db_phone_raw = row.get("user_phone") or row.get("phone")
    db_phone = _normalize_phone(db_phone_raw)
    tg_phone = _normalize_phone(phone)

    if not db_phone:
        return jsonify(status="missing_phone", bot_text=TG_NO_PHONE_TEXT)

    if not tg_phone or db_phone != tg_phone:
        return jsonify(status="phone_mismatch", bot_text=TG_MISMATCH_TEXT)

    try:
        update_data = {
            RECOVERY_CHAT_FIELD: str(chat_id),
            "user_tg_id": str(chat_id),
        }
        client.table(table).update(update_data).eq("user_id", user_id).execute()

    except Exception as exc:
        log.error("link_recovery update failed: %s", exc)
        return jsonify(error="server_error", bot_text="Не вдалося зберегти Telegram."), 500

    clear_cache(table)
    return jsonify(status="ok", bot_text=TG_SUCCESS_TEXT)
