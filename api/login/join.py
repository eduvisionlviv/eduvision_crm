# api/login/join.py
import os
import re
import secrets
import datetime as dt
import logging
from typing import Optional, Tuple

from flask import Blueprint, request, jsonify, make_response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from api.coreapiserver import get_client_for_table, clear_cache, describe_appwrite_config
from services import tg_bot
from services.gmail import send_email, GmailConfigError

bp = Blueprint("login_join", __name__, url_prefix="/api/login")
bp_auth = Blueprint("login_auth", __name__, url_prefix="/api/auth")
bp_tg = Blueprint("login_tg", __name__, url_prefix="/api/tg")
bps = (bp_auth, bp_tg)

log = logging.getLogger("login.join")

# ── Cookie / TTL
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

# ── Перевірка пароля: підтримуємо і хеші, і plaintext (для зворотно сумісних акаунтів)
try:
    import bcrypt
except Exception:  # pragma: no cover - бібліотека має бути встановлена
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
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        if isinstance(value, (int, float)):
            return bool(int(value))
    except (TypeError, ValueError):
        pass
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
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
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
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


def _payload_from_row(row: dict):
    payload = {
        "user_id":      row.get("user_id"),
        "user_name":    row.get("user_name"),
        "user_phone":   row.get("user_phone"),
        "user_access":  row.get("user_access"),
        "extra_access": row.get("extra_access"),
    }
    payload["need_tg_setup"] = _need_tg_setup(row)
    return payload


def _mask_email(e: str) -> str:
    if not e:
        return "-"
    e = e.strip().lower()
    m = re.match(r"^([^@]{0,3})[^@]*(@.*)$", e)
    return (m.group(1) + "***" + m.group(2)) if m else e[:2] + "***"


def _fail_invalid():
    return jsonify(error="invalid_credentials", message="Невірний email або пароль"), 401


def _need_tg_setup(row: dict) -> bool:
    """Telegram-підключення є обов'язковим незалежно від uni_base."""
    recovery = _get_recovery_chat(row)
    return not bool(recovery)


def _get_recovery_chat(row: dict) -> Optional[str]:
    return row.get(RECOVERY_CHAT_FIELD) or row.get("recovery_pass_tg")


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    core = None
    if digits.startswith("380") and len(digits) >= 12:
        core = digits[-9:]
    elif digits.startswith("0") and len(digits) >= 10:
        core = digits[-9:]
    elif len(digits) == 9:
        core = digits

    if not core or len(core) != 9:
        return None

    return "+380" + core


def _get_link_serializer() -> URLSafeTimedSerializer:
    """Return a deterministic secret for signing Telegram link tokens."""

    secret = None
    for key in ("TG_LINK_SECRET", "SECRET_KEY", "HDD", "HDD2"):
        value = os.getenv(key)
        if value:
            secret = value
            break

    if not secret:
        raise RuntimeError(
            "Задайте TG_LINK_SECRET або SECRET_KEY (можна використати HDD/HDD2) для Telegram-прив'язки"
        )

    return URLSafeTimedSerializer(secret_key=secret, salt="eduvision-tg-link")


def _sign_user_token(user_id: int) -> str:
    serializer = _get_link_serializer()
    return serializer.dumps({"user_id": user_id})


def _unsign_user_token(token: str) -> int:
    serializer = _get_link_serializer()
    data = serializer.loads(token, max_age=TG_LINK_TOKEN_TTL_HRS * 3600)
    return int(data.get("user_id"))


def _issue_session(contacts_client, user_id: int) -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    exp   = _exp_iso()
    contacts_client.table("contacts").update({
        "auth_tokens": token,
        "expires_at":  exp
    }).eq("user_id", user_id).execute()
    return token, exp


def _build_reset_link(token: str) -> str:
    if PUBLIC_APP_URL:
        base = PUBLIC_APP_URL.rstrip("/") + "/"
    else:
        base = request.host_url
    return f"{base}#reset?token={token}"


def _store_reset_code(user_id: int) -> Tuple[str, str]:
    contacts = get_client_for_table("contacts")
    token = secrets.token_urlsafe(32)
    issued = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    contacts.table("contacts").update({
        RESET_CODE_FIELD: token,
        RESET_TIME_FIELD: issued,
    }).eq("user_id", user_id).execute()
    clear_cache("contacts")
    return token, issued


def _resolve_user_by_token(token: str) -> Optional[dict]:
    contacts = get_client_for_table("contacts")
    try:
        row = contacts.table("contacts").select(
            "user_id,user_name,user_phone,user_email,user_access,extra_access,{tg}".format(
                tg=RECOVERY_CHAT_FIELD
            )
        ).eq("auth_tokens", token).gt("expires_at", _now_iso()).single().execute().data
    except Exception:
        row = None
    return row


def _get_user_for_request() -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return _resolve_user_by_token(token)


def _send_tg_reset(chat_id: str, link: str) -> None:
    chat = int(chat_id)
    tg_bot.send_message_httpx(chat, (
        "🔒 Відновлення доступу до EduVision\n"
        "Натисніть на посилання, щоб задати новий пароль:\n"
        f"{link}"
    ))


def _send_email_reset(email: str, link: str, subject: str) -> None:
    html = (
        "<p>Щоб відновити доступ до EduVision, перейдіть за посиланням і задайте новий пароль:</p>"
        f"<p><a href=\"{link}\">Відкрити форму скидання паролю</a></p>"
        "<p>Посилання дійсне обмежений час. Якщо ви не ініціювали запит – просто ігноруйте цей лист.</p>"
    )
    send_email(email, subject, html)


def _send_tg_link_email(email: str, bot_link: str) -> None:
    html = (
        "<p>Щоб захистити ваш акаунт EduVision, підключіть Telegram-бота Helen Doron English.</p>"
        f"<p><a href=\"{bot_link}\">👉 Відкрити бота</a></p>"
        "<p>Натисніть Start у боті та поділіться номером телефону.</p>"
        "<p>Поверніться в EduVision, оновіть сторінку та зайдіть ще раз.</p>"
    )
    send_email(
        email,
        "Підключення Telegram-бота Helen Doron English для EduVision",
        html,
    )


def _get_reset_row(token: str) -> Tuple[Optional[dict], Optional[str]]:
    contacts = get_client_for_table("contacts")
    try:
        row = contacts.table("contacts").select(
            "user_id,user_email,user_name,{code},{ts}".format(
                code=RESET_CODE_FIELD,
                ts=RESET_TIME_FIELD,
            )
        ).eq(RESET_CODE_FIELD, token).single().execute().data
    except Exception:
        return None, "invalid"

    if not row or not row.get(RESET_CODE_FIELD):
        return None, "invalid"

    issued = _parse_timestamp(row.get(RESET_TIME_FIELD))
    if not issued:
        return None, "invalid"

    expires_at = issued + dt.timedelta(minutes=RESET_TOKEN_TTL_MIN)
    if expires_at <= _utcnow():
        return None, "expired"

    return row, None


def _clear_reset_code(user_id: int) -> None:
    contacts = get_client_for_table("contacts")
    try:
        contacts.table("contacts").update({
            RESET_CODE_FIELD: None,
            RESET_TIME_FIELD: None,
        }).eq("user_id", user_id).execute()
    except Exception as exc:
        log.warning("Не вдалося очистити код відновлення user_id=%s: %s", user_id, exc)
    clear_cache("contacts")


# ─────────────────────────────────────────────────────────────
# POST /api/login/register — заявка в register
# body: { user_email, user_name, user_phone, pass_email }
# ─────────────────────────────────────────────────────────────
@bp.post("/register")
def register_user():
    b = request.get_json(silent=True) or {}
    email = (b.get("user_email") or "").strip().lower()
    name  = (b.get("user_name")  or "").strip()
    phone = (b.get("user_phone") or "").strip()
    pwd   =  (b.get("pass_email") or "")

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

        res = register.table("register").insert({
            "user_email": email,
            "user_name":  name,
            "user_phone": phone,
            "pass_email": hash_password(pwd),
        }).execute()

        if not getattr(res, "data", None):
            cfg = describe_appwrite_config()
            detail = res.error or "insert returned no data"
            log.error(
                "register insert returned no data for %s — reason=%s config=%s",
                _mask_email(email),
                detail,
                cfg,
            )
            body = {"error": "server_error", "message": "Не вдалося створити заявку."}
            if DEBUG_ERRORS:
                body["detail"] = detail
                body["config"] = cfg
            return jsonify(body), 500

        return jsonify(message="Заявку прийнято. Очікуйте підтвердження адміністратора."), 200

    except Exception as e:
        cfg = describe_appwrite_config()
        body = {"error": "server_error", "message": "Не вдалося створити заявку."}
        if DEBUG_ERRORS:
            body["detail"] = str(e)
            body["config"] = cfg
        log.error("register failed for %s: %s config=%s", _mask_email(email), e, cfg)
        return jsonify(body), 500


# ─────────────────────────────────────────────────────────────
# POST /api/login/join — логін
# body: { email, password } або { user_email, pass_email }
# ─────────────────────────────────────────────────────────────
@bp.post("/join")
def join():
    b = request.get_json(silent=True) or {}
    email = (b.get("email") or b.get("user_email") or "").strip().lower()
    pwd   =  (b.get("password") or b.get("pass_email") or "")

    if not email or not pwd:
        return _fail_invalid()

    contacts = get_client_for_table("contacts")

    try:
        row = contacts.table("contacts").select(
            "user_id,user_email,user_name,user_phone,user_access,extra_access,pass_email,{tg}".format(
                tg=RECOVERY_CHAT_FIELD
            )
        ).eq("user_email", email).single().execute().data
    except Exception:
        row = None

    if not row:
        log.info("login fail (no user): %s", _mask_email(email))
        return _fail_invalid()

    stored = row.get("pass_email") or ""
    if not _check_pwd(pwd, stored):
        log.info("login fail (bad pwd): %s", _mask_email(email))
        return _fail_invalid()

    if not _is_bcrypt_hash(stored):
        try:
            new_hash = hash_password(pwd)
            contacts.table("contacts").update({"pass_email": new_hash}).eq("user_id", row["user_id"]).execute()
            row["pass_email"] = new_hash
        except Exception as exc:
            log.warning("Не вдалося оновити пароль до bcrypt для user_id=%s: %s", row.get("user_id"), exc)

    try:
        token, _ = _issue_session(contacts, row["user_id"])
    except Exception as e:
        body = {"error":"server_error", "message":"Не вдалося видати сесію"}
        if DEBUG_ERRORS: body["detail"] = str(e)
        log.error("set auth token failed for user_id=%s: %s", row.get("user_id"), e)
        return jsonify(body), 500

    payload = _payload_from_row(row)
    resp = make_response(jsonify(ok=True, need_tg_setup=payload["need_tg_setup"]))
    return _set_cookie(resp, token)


# ─────────────────────────────────────────────────────────────
# GET /api/login/me — плоскі поля для фронту
# ────────────────────────────────────────────────────────────
@bp.get("/me")
def me():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify(error="unauthorized"), 401

    row = _resolve_user_by_token(token)

    if not row:
        return jsonify(error="unauthorized"), 401

    payload = _payload_from_row(row)
    return jsonify(ok=True, **payload, user=payload)


# ─────────────────────────────────────────────────────────────
# POST /api/login/logout — вихід
# ─────────────────────────────────────────────────────────────
@bp.post("/logout")
def logout():
    token = request.cookies.get(COOKIE_NAME)
    contacts = get_client_for_table("contacts")
    if token:
        try:
            contacts.table("contacts").update({"auth_tokens": None, "expires_at": None}) \
                    .eq("auth_tokens", token).execute()
        except Exception as e:
            log.info("logout token clear failed: %s", e)
    resp = make_response(jsonify(ok=True))
    resp.set_cookie(COOKIE_NAME, "", path="/", max_age=0,
                    httponly=True, secure=COOKIE_SECURE, samesite="Lax")
    return resp


# ─────────────────────────────────────────────────────────────
# POST /api/login/forgot — запит на скидання паролю
# ─────────────────────────────────────────────────────────────
@bp.post("/forgot")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not EMAIL_RX.match(email):
        return jsonify(message=FORGOT_GENERIC_MSG), 200

    contacts = get_client_for_table("contacts")
    try:
        row = contacts.table("contacts").select(
            "user_id,user_email,user_name,{tg}".format(tg=RECOVERY_CHAT_FIELD)
        ).eq("user_email", email).single().execute().data
    except Exception:
        row = None

    if not row:
        return jsonify(message=FORGOT_GENERIC_MSG), 200

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

    token, _ = _store_reset_code(row["user_id"])
    link = _build_reset_link(token)

    try:
        if method == "tg":
            _send_tg_reset(recovery_chat, link)
            msg = FORGOT_TG_MSG
        else:
            _send_email_reset(email, link, "Скидання паролю EduVision")
            msg = FORGOT_EMAIL_MSG
    except GmailConfigError as exc:
        log.warning(
            "email recovery disabled for %s: %s", _mask_email(email), exc
        )
        return jsonify(message=FORGOT_EMAIL_DISABLED), 200
    except Exception as exc:
        log.error("reset delivery failed for %s: %s", _mask_email(email), exc)
        return jsonify(error="delivery_failed", message="Не вдалося надіслати інструкції."), 500

    body = {"message": msg}
    if LOGIN_DEBUG:
        body["debug_link"] = link
    return jsonify(body)


# ─────────────────────────────────────────────────────────────
# POST /api/login/reset — новий пароль за токеном
# ─────────────────────────────────────────────────────────────
@bp.post("/reset")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify(error="validation_error", message="Пароль має бути від 6 символів"), 400
    if not token:
        return jsonify(error="validation_error", message="Некоректний токен"), 400

    row, reason = _get_reset_row(token)
    if not row:
        message = RESET_LINK_EXPIRED_MSG if reason == "expired" else RESET_LINK_INVALID_MSG
        return jsonify(error="invalid_token", message=message), 400

    contacts = get_client_for_table("contacts")
    pass_hash = hash_password(new_password)

    try:
        contacts.table("contacts").update({"pass_email": pass_hash}).eq("user_id", row["user_id"]).execute()
    except Exception as exc:
        log.error("reset password update failed user_id=%s: %s", row["user_id"], exc)
        return jsonify(error="server_error", message="Не вдалося оновити пароль"), 500

    _clear_reset_code(row["user_id"])

    try:
        token_value, _ = _issue_session(contacts, row["user_id"])
    except Exception:
        token_value = None

    resp = make_response(jsonify(ok=True))
    if token_value:
        _set_cookie(resp, token_value)
    return resp


# ─────────────────────────────────────────────────────────────
# POST /api/auth/send_tg_link — лист із посиланням на бота
# ─────────────────────────────────────────────────────────────
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
        token = _sign_user_token(user["user_id"])
    except RuntimeError as exc:
        log.error("sign token misconfigured for user_id=%s: %s", user.get("user_id"), exc)
        return jsonify(error="config_error", message=str(exc)), 500
    except Exception as exc:
        log.error("sign token failed for user_id=%s: %s", user.get("user_id"), exc)
        return jsonify(error="server_error", message="Не вдалося сформувати посилання"), 500

    safe_token = token.replace(".", "-")
    link = f"https://t.me/{bot_username}?start={safe_token}"

    try:
        _send_tg_link_email(user.get("user_email"), link)
    except GmailConfigError as exc:
        log.warning("gmail config missing — returning bot link instead: %s", exc)
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


# ─────────────────────────────────────────────────────────────
# POST /api/tg/link_recovery — виклик із Telegram-бота
# ─────────────────────────────────────────────────────────────
@bp_tg.post("/link_recovery")
def link_recovery():
    data = request.get_json(silent=True) or {}
    token = (data.get("user_token") or "").strip()
    chat_id = data.get("chat_id")
    phone = data.get("phone") or ""

    if not (token and chat_id and phone):
        return jsonify(error="validation_error", bot_text="Недостатньо даних."), 400

    try:
        user_id = _unsign_user_token(token)
    except (BadSignature, SignatureExpired) as exc:
        log.warning("link_recovery invalid token: %s", exc)
        return jsonify(error="invalid_token", bot_text=TG_BAD_TOKEN_TEXT), 400

    contacts = get_client_for_table("contacts")
    try:
        row = contacts.table("contacts").select("user_id,user_phone").eq("user_id", user_id).single().execute().data
    except Exception as exc:
        log.error("link_recovery user lookup failed: %s", exc)
        row = None

    if not row:
        return jsonify(error="not_found", bot_text="Акаунт не знайдено."), 404

    db_phone = _normalize_phone(row.get("user_phone"))
    tg_phone = _normalize_phone(phone)

    if not db_phone:
        return jsonify(status="missing_phone", bot_text=TG_NO_PHONE_TEXT)

    if not tg_phone or db_phone != tg_phone:
        return jsonify(status="phone_mismatch", bot_text=TG_MISMATCH_TEXT)

    try:
        update_data = {
            RECOVERY_CHAT_FIELD: str(chat_id),  # recovery_tg_id
            "user_tg_id": str(chat_id),         # основний tg_id користувача
        }
        contacts.table("contacts").update(update_data).eq("user_id", user_id).execute()

    except Exception as exc:
        log.error("link_recovery update failed: %s", exc)
        return jsonify(error="server_error", bot_text="Не вдалося зберегти Telegram."), 500

    clear_cache("contacts")
    return jsonify(status="ok", bot_text=TG_SUCCESS_TEXT)
