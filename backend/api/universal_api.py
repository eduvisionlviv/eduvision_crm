# backend/api/universal_api.py
import re
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["pb-universal"])

# ───────────────────────────────
# 🔖 Реєстр відомих таблиць
# ───────────────────────────────
KNOWN_TABLES: Dict[str, str] = {
    "user_staff": "user_staff",
    "reg": "reg",
    # "courses": "courses",
    # "centers": "centers",
}


class CRUDPayload(BaseModel):
    data: Dict[str, Any]


# ───────────────────────────────
# 🧩 Допоміжне: Робота з типами
# ───────────────────────────────
def resolve_collection(table: str) -> str:
    if table not in KNOWN_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown table '{table}'. Додай її у KNOWN_TABLES.",
        )
    return KNOWN_TABLES[table]


def clean_rich_text(text: str) -> str:
    """Видаляє HTML-теги, якщо поле було RichText (наприклад <p>value</p>)."""
    # Якщо рядок виглядає як HTML (починається з тега), чистимо його
    if text and "<" in text and ">" in text:
        return re.sub(r'<[^>]+>', '', text).strip()
    return text


def sanitize_record(record: Any) -> Dict[str, Any]:
    """
    Конвертує запис у словник і очищає рядкові поля від HTML-сміття.
    """
    # 1. Конвертація в dict
    if hasattr(record, "model_dump"):
        data = record.model_dump()
    elif hasattr(record, "to_dict"):
        data = record.to_dict()
    elif isinstance(record, dict):
        data = record
    else:
        data = getattr(record, "__dict__", {})

    # 2. Очищення полів
    clean_data = {}
    for key, val in data.items():
        if isinstance(val, str):
            clean_data[key] = clean_rich_text(val)
        else:
            clean_data[key] = val
    return clean_data


def build_filter_expr(filters: List[str]) -> str:
    """
    filters=col:op:value → PocketBase filter string.
    Враховує типи: числа, true/false/null не бере в лапки.
    """
    exprs: List[str] = []
    for raw in filters:
        parts = raw.split(":", 3)
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail=f"Bad filter: {raw}")
        col, op, val = parts

        # Визначаємо, чи треба брати значення в лапки
        # Якщо це число, bool або null - лапки не потрібні для SQL PocketBase
        if val.lower() in ["true", "false", "null"]:
            safe_val = val.lower()
        elif val.replace(".", "", 1).isdigit(): # Проста перевірка на число
            safe_val = val
        else:
            safe_val = f"'{val}'"

        if op == "eq":
            exprs.append(f"{col} = {safe_val}")
        elif op == "neq":
            exprs.append(f"{col} != {safe_val}")
        elif op == "gt":
            exprs.append(f"{col} > {safe_val}")
        elif op == "lt":
            exprs.append(f"{col} < {safe_val}")
        elif op == "gte":
            exprs.append(f"{col} >= {safe_val}")
        elif op == "lte":
            exprs.append(f"{col} <= {safe_val}")
        elif op in ("like", "ilike"):
            # Для like завжди потрібні лапки, бо це рядкова операція
            exprs.append(f"{col} ~ '{val}'")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operator: {op}")

    return " && ".join(exprs)


# ───────────────────────────────
# 🔍 GET /api/pb/<table>
# ───────────────────────────────
@router.get("/pb/{table}")
def pb_get(
    table: str,
    filters: Optional[List[str]] = Query(default=None),
):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    collection = resolve_collection(table)

    try:
        if not filters:
            records = client.collection(collection).get_full_list()
            # Проходимось по записах і чистимо їх
            return [sanitize_record(r) for r in records]

        filter_str = build_filter_expr(filters)
        
        page_res = client.collection(collection).get_list(
            page=1,
            per_page=500,
            filter=filter_str,
        )
        items = page_res.items if hasattr(page_res, "items") else []
        # Теж чистимо
        return [sanitize_record(r) for r in items]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# ➕ POST /api/pb/<table>
# ───────────────────────────────
@router.post("/pb/{table}")
def pb_create(table: str, payload: CRUDPayload):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    collection = resolve_collection(table)

    try:
        record = client.collection(collection).create(payload.data)
        # Повертаємо чистий запис
        return sanitize_record(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# ✏️ PATCH /api/pb/<table>/<id>
# ───────────────────────────────
@router.patch("/pb/{table}/{record_id}")
def pb_update(table: str, record_id: str, payload: CRUDPayload):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    collection = resolve_collection(table)

    try:
        record = client.collection(collection).update(record_id, payload.data)
        return sanitize_record(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# 🗑 DELETE /api/pb/<table>/<id>
# ───────────────────────────────
@router.delete("/pb/{table}/{record_id}")
def pb_delete(table: str, record_id: str):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    collection = resolve_collection(table)

    try:
        client.collection(collection).delete(record_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
