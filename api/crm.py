"""Основні API для CRM навчального закладу.

Модуль закриває потреби в роботі з учнями, батьками, курсами,
оплатами та банківськими ключами для інтеграції з API банку.
Побудовано навколо Appwrite і використовує існуючу сесію
(кука `edu_session`), яку видає /api/login/join.
"""
from __future__ import annotations

import datetime as dt
import base64
import os
from functools import wraps
from typing import Iterable, Optional

from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, jsonify, request

from api.coreapiserver import get_client_for_table
from api.login.join import _get_user_for_request

bp = Blueprint("crm", __name__, url_prefix="/api/crm")

# Ролі, які підтримує CRM
ROLES = {
    "admin",
    "lc_manager",
    "lc",
    "teacher",
    "parent",
    "student",
}

CRM_TABLES = {
    "students": "crm_students",
    "parents": "crm_parents",
    "courses": "crm_courses",
    "enrollments": "crm_enrollments",
    "payments": "crm_payments",
    "bank_keys": "crm_bank_keys",
    "bank_accounts": "crm_bank_accounts",
}

PAYMENT_TYPES = {"year", "month", "lesson"}


# ──────────────────────────── Утиліти ────────────────────────────

def _get_role() -> Optional[str]:
    user = _get_user_for_request()
    if not user:
        return None
    role = user.get("user_access") or ""
    return role.lower()


def require_role(allowed: Iterable[str]):
    """Декоратор для обмеження доступу за ролями."""

    allowed_set = {r.lower() for r in allowed}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = _get_role()
            if not role:
                return jsonify(error="unauthorized"), 401
            if role not in allowed_set:
                return jsonify(error="forbidden"), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _table(name: str):
    client = get_client_for_table(name)
    table_name = CRM_TABLES.get(name, name)
    return client.table(table_name)


def _calc_age(birth_date: str) -> Optional[int]:
    if not birth_date:
        return None
    try:
        if "T" in birth_date:
            parsed = dt.datetime.fromisoformat(birth_date)
            born = parsed.date()
        else:
            born = dt.date.fromisoformat(birth_date)
    except ValueError:
        return None

    today = dt.date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return max(years, 0)


def _augment_student(doc: dict) -> dict:
    result = dict(doc or {})
    age = _calc_age(result.get("birth_date"))
    if age is not None:
        result["age_years"] = age
    return result


def _safe_mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _get_cipher() -> Fernet:
    secret = os.getenv("BANK_ENCRYPTION_KEY") or ""
    if not secret:
        raise RuntimeError("BANK_ENCRYPTION_KEY is not configured")

    # Дозволяємо як готовий base64, так і сирий ключ у hex/utf-8
    try:
        key_bytes = base64.urlsafe_b64decode(secret)
    except Exception:  # noqa: BLE001
        key_bytes = secret.encode()
        key_bytes = base64.urlsafe_b64encode(key_bytes.ljust(32, b"0")[:32])

    try:
        return Fernet(key_bytes)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("BANK_ENCRYPTION_KEY is invalid for Fernet") from exc


def _encrypt(value: str) -> str:
    cipher = _get_cipher()
    return cipher.encrypt(value.encode()).decode()


def _make_mask(account_number: str) -> str:
    if not account_number:
        return ""
    visible = account_number[-4:]
    return f"***{visible}"


# ──────────────────────────── Метадані ────────────────────────────


@bp.get("/meta")
def meta():
    """Повертає опис модулів та доступні ролі."""

    return jsonify(
        ok=True,
        roles=sorted(ROLES),
        modules=[
            {
                "id": "students",
                "title": "Учні",
                "description": "Профілі дітей 2–18 років з автоматичним підрахунком віку",
            },
            {
                "id": "parents",
                "title": "Батьки/опікуни",
                "description": "Контактні дані дорослих та зв’язок з учнями",
            },
            {
                "id": "courses",
                "title": "Курси",
                "description": "Навчальні програми з назвами та віковими обмеженнями",
            },
            {
                "id": "enrollments",
                "title": "Записи на курс",
                "description": "Прив’язка учнів до курсів з датою старту та статусом",
            },
            {
                "id": "payments",
                "title": "Оплати",
                "description": "Оплата за рік/місяць/заняття з прив’язкою до учня",
            },
            {
                "id": "bank_keys",
                "title": "Банківські ключі",
                "description": "Безпечне збереження API ключів для авто-зарахування платежів",
            },
        ],
    )


# ──────────────────────────── Учні ────────────────────────────────


@bp.get("/students")
@require_role({"admin", "lc_manager", "lc", "teacher"})
def list_students():
    table = _table("students")
    rows = table.select("*").execute().data or []
    return jsonify(students=[_augment_student(r) for r in rows])


@bp.post("/students")
@require_role({"admin", "lc_manager", "lc"})
def create_student():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        "full_name": payload.get("full_name"),
        "birth_date": payload.get("birth_date"),
        "parent_id": payload.get("parent_id"),
        "notes": payload.get("notes"),
    }
    res = _table("students").insert(data).execute().data
    return jsonify(student=_augment_student(res)), 201


@bp.get("/students/<student_id>/age")
@require_role({"admin", "lc_manager", "lc", "teacher", "parent"})
def student_age(student_id: str):
    table = _table("students")
    row = table.select("*").eq("$id", student_id).single().execute().data
    if not row:
        return jsonify(error="not_found"), 404
    age = _calc_age(row.get("birth_date"))
    return jsonify(student_id=student_id, age_years=age)


# ──────────────────────────── Батьки ──────────────────────────────


@bp.get("/parents")
@require_role({"admin", "lc_manager", "lc"})
def list_parents():
    rows = _table("parents").select("*").execute().data or []
    return jsonify(parents=rows)


@bp.post("/parents")
@require_role({"admin", "lc_manager", "lc"})
def create_parent():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        "full_name": payload.get("full_name"),
        "phone": payload.get("phone"),
        "email": payload.get("email"),
        "notes": payload.get("notes"),
    }
    res = _table("parents").insert(data).execute().data
    return jsonify(parent=res), 201


# ──────────────────────────── Курси ───────────────────────────────


@bp.get("/courses")
@require_role({"admin", "lc_manager", "lc", "teacher"})
def list_courses():
    rows = _table("courses").select("*").execute().data or []
    return jsonify(courses=rows)


@bp.post("/courses")
@require_role({"admin", "lc_manager", "lc"})
def create_course():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        "name": payload.get("name"),
        "age_from": payload.get("age_from"),
        "age_to": payload.get("age_to"),
        "description": payload.get("description"),
    }
    res = _table("courses").insert(data).execute().data
    return jsonify(course=res), 201


# ──────────────────────────── Записи на курс ─────────────────────


@bp.get("/enrollments")
@require_role({"admin", "lc_manager", "lc", "teacher"})
def list_enrollments():
    rows = _table("enrollments").select("*").execute().data or []
    return jsonify(enrollments=rows)


@bp.post("/enrollments")
@require_role({"admin", "lc_manager", "lc"})
def create_enrollment():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        "student_id": payload.get("student_id"),
        "course_id": payload.get("course_id"),
        "start_date": payload.get("start_date"),
        "status": payload.get("status", "active"),
    }
    res = _table("enrollments").insert(data).execute().data
    return jsonify(enrollment=res), 201


# ──────────────────────────── Оплати ─────────────────────────────


@bp.get("/payments")
@require_role({"admin", "lc_manager", "lc"})
def list_payments():
    rows = _table("payments").select("*").execute().data or []
    return jsonify(payments=rows)


@bp.post("/payments")
@require_role({"admin", "lc_manager", "lc"})
def create_payment():
    payload = request.get_json(force=True, silent=True) or {}
    payment_type = (payload.get("payment_type") or "").lower()
    if payment_type not in PAYMENT_TYPES:
        return jsonify(error="invalid_payment_type", allowed=sorted(PAYMENT_TYPES)), 400

    data = {
        "student_id": payload.get("student_id"),
        "amount": payload.get("amount"),
        "currency": payload.get("currency", "UAH"),
        "payment_type": payment_type,
        "period": payload.get("period"),
        "comment": payload.get("comment"),
    }
    res = _table("payments").insert(data).execute().data
    return jsonify(payment=res), 201


# ──────────────────────────── Банківські ключі ───────────────────


@bp.get("/bank/keys")
@require_role({"admin", "lc_manager"})
def list_bank_keys():
    rows = _table("bank_keys").select("*").execute().data or []
    sanitized = []
    for row in rows:
        sanitized.append(
            {
                "provider": row.get("provider"),
                "api_key_id": _safe_mask(row.get("api_key_id")),
                "webhook_secret": _safe_mask(row.get("webhook_secret")),
                "created_at": row.get("$createdAt")
                               or row.get("created_at")
                               or row.get("creation_date")
                               or row.get("creationDate")
                               or row.get("sCreatedAt"),
                "created_by": row.get("created_by"),
            }
        )
    return jsonify(keys=sanitized)


@bp.post("/bank/keys")
@require_role({"admin", "lc_manager"})
def store_bank_keys():
    payload = request.get_json(force=True, silent=True) or {}
    role = _get_role()
    data = {
        "provider": payload.get("provider"),
        "api_key_id": payload.get("api_key_id"),
        "api_secret": payload.get("api_secret"),
        "webhook_secret": payload.get("webhook_secret"),
        "created_by": role,
    }
    _table("bank_keys").insert(data).execute()
    return jsonify(ok=True, message="Ключі збережено"), 201


# ──────────────────────────── Банківські рахунки (шифровані) ─────


SUPPORTED_BANKS = {"privatbank", "monobank"}


@bp.get("/bank/accounts")
@require_role({"admin", "lc_manager"})
def list_bank_accounts():
    rows = _table("bank_accounts").select("*").execute().data or []
    sanitized = []
    for row in rows:
        mask = row.get("account_mask") or _safe_mask(row.get("account_number_hint"))
        sanitized.append(
            {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "provider": row.get("provider"),
                "provider_api": row.get("provider_api"),
                "account_mask": mask,
                "encryption": row.get("encryption_method", "fernet"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )
    return jsonify(accounts=sanitized)


@bp.post("/bank/accounts")
@require_role({"admin", "lc_manager"})
def store_bank_account():
    payload = request.get_json(force=True, silent=True) or {}

    provider = (payload.get("provider") or "").lower()
    if provider not in SUPPORTED_BANKS:
        return jsonify(error="unsupported_provider", allowed=sorted(SUPPORTED_BANKS)), 400

    provider_api = payload.get("provider_api") or provider
    user_id = payload.get("user_id")
    account_number = payload.get("account_number") or ""
    api_key = payload.get("api_key") or ""

    if not user_id:
        return jsonify(error="user_id_required"), 400
    if not account_number or not api_key:
        return jsonify(error="missing_credentials", message="Потрібні account_number та api_key"), 400

    try:
        account_mask = _make_mask(account_number)
        encrypted_account = _encrypt(account_number)
        encrypted_api_key = _encrypt(api_key)
    except InvalidToken:
        return jsonify(error="encryption_failed", message="Неправильний BANK_ENCRYPTION_KEY"), 500
    except RuntimeError as exc:  # noqa: BLE001
        return jsonify(error="config_error", message=str(exc)), 500

    data = {
        "user_id": user_id,
        "provider": provider,
        "provider_api": provider_api,
        "account_mask": account_mask,
        "account_number_encrypted": encrypted_account,
        "api_key_encrypted": encrypted_api_key,
        "encryption_method": "fernet",
    }

    _table("bank_accounts").insert(data).execute()
    return jsonify(ok=True, message="Банківські реквізити збережено", account_mask=account_mask), 201


__all__ = ["bp"]
