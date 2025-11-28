"""Основні API для CRM навчального закладу.

Модуль закриває потреби в роботі з учнями, батьками, курсами,
оплатами та банківськими ключами для інтеграції з API банку.
Побудовано навколо Appwrite і використовує існуючу сесію
(кука `edu_session`), яку видає /api/login/join.
"""
from __future__ import annotations

import datetime as dt
from functools import wraps
from typing import Iterable, Optional

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


def _validate_required_fields(data: dict, required_fields: Iterable[str]):
    missing = []
    for field in required_fields:
        value = data.get(field)
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and value.strip() == "":
            missing.append(field)

    if missing:
        return jsonify(error="missing_fields", required=list(required_fields), missing=missing), 400

    return None


def _safe_mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


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
        "enrollment_date": payload.get("enrollment_date"),
        "grade_level": payload.get("grade_level"),
        "student_status": payload.get("student_status") or "active",
    }
    missing_resp = _validate_required_fields(
        data,
        [
            "full_name",
            "birth_date",
            "parent_id",
            "enrollment_date",
            "grade_level",
            "student_status",
        ],
    )
    if missing_resp:
        return missing_resp
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
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "max_participants": payload.get("max_participants"),
    }
    missing_resp = _validate_required_fields(
        data, ["name", "start_time", "end_time", "max_participants"]
    )
    if missing_resp:
        return missing_resp
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
        "completion_date": payload.get("completion_date"),
    }
    missing_resp = _validate_required_fields(
        data, ["student_id", "course_id", "start_date", "status", "completion_date"]
    )
    if missing_resp:
        return missing_resp
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
        "payment_id": payload.get("payment_id"),
        "payment_method": payload.get("payment_method"),
        "payment_date": payload.get("payment_date"),
    }
    missing_resp = _validate_required_fields(
        data,
        ["student_id", "amount", "payment_type", "payment_id", "payment_method", "payment_date"],
    )
    if missing_resp:
        return missing_resp
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
                "created_at": row.get("$createdAt") or row.get("created_at"),
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


__all__ = ["bp"]
