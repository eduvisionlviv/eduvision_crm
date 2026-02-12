# backend/api/universal_api.py
import re
import json
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["pb-universal"])

# ───────────────────────────────
# 🔖 Реєстр відомих таблиць (Whitelist)
# ───────────────────────────────
KNOWN_TABLES: Dict[str, str] = {
    "user_staff": "user_staff",
    "reg": "reg",
    "lc": "lc",
    # Додавайте сюди нові таблиці по мірі створення в PocketBase
    # "courses": "courses",
    # "leads": "leads",
}

class CRUDPayload(BaseModel):
    data: Dict[str, Any]

class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    page: int
    perPage: int
    totalItems: int
    totalPages: int

# ───────────────────────────────
# 🧩 Допоміжні функції
# ───────────────────────────────
def resolve_collection(table: str) -> str:
    if table not in KNOWN_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown table '{table}'. Додай її у KNOWN_TABLES в universal_api.py.",
        )
    return KNOWN_TABLES[table]

def clean_rich_text(text: str) -> str:
    """Видаляє HTML-теги з RichText полів."""
    if text and isinstance(text, str) and "<" in text and ">" in text:
        return re.sub(r'<[^>]+>', '', text).strip()
    return text

def sanitize_record(record: Any) -> Dict[str, Any]:
    """Конвертує запис у словник і чистить сміття (HTML)."""
    if hasattr(record, "model_dump"):
        data = record.model_dump()
    elif hasattr(record, "to_dict"):
        data = record.to_dict()
    elif isinstance(record, dict):
        data = record
    else:
        data = getattr(record, "__dict__", {})

    clean_data = {}
    for key, val in data.items():
        if isinstance(val, str):
            clean_data[key] = clean_rich_text(val)
        else:
            clean_data[key] = val
    return clean_data

def build_filter_expr(filters: List[str]) -> str:
    """
    Конвертує прості фільтри format=col:op:val у PocketBase синтаксис.
    """
    exprs: List[str] = []
    for raw in filters:
        parts = raw.split(":", 3)
        if len(parts) != 3:
            continue # Пропускаємо биті фільтри
        col, op, val = parts

        # Обробка типів (числа та булеві не беремо в лапки)
        if val.lower() in ["true", "false", "null"]:
            safe_val = val.lower()
        elif val.replace(".", "", 1).isdigit():
            safe_val = val
        else:
            safe_val = f"'{val}'"

        if op == "eq": exprs.append(f"{col} = {safe_val}")
        elif op == "neq": exprs.append(f"{col} != {safe_val}")
        elif op == "gt": exprs.append(f"{col} > {safe_val}")
        elif op == "lt": exprs.append(f"{col} < {safe_val}")
        elif op == "gte": exprs.append(f"{col} >= {safe_val}")
        elif op == "lte": exprs.append(f"{col} <= {safe_val}")
        elif op in ("like", "ilike"): exprs.append(f"{col} ~ '{val}'")

    return " && ".join(exprs)

# ───────────────────────────────
# 🔍 GET /api/pb/<table> - УНІВЕРСАЛЬНИЙ ПОШУК
# ───────────────────────────────
@router.get("/pb/{table}")
def pb_get(
    table: str,
    page: int = Query(1, ge=1, description="Номер сторінки"),
    perPage: int = Query(50, ge=1, le=500, description="Кількість записів на сторінку"),
    sort: Optional[str] = Query(None, description="Поле сортування (напр. '-created')"),
    expand: Optional[str] = Query(None, description="Зв'язки (напр. 'user_id,course_id')"),
    filters: Optional[List[str]] = Query(None, description="Прості фільтри col:op:val"),
    filter_raw: Optional[str] = Query(None, description="Сирий SQL-фільтр PocketBase (напр. '(a=1 || b=2)')"),
    full_list: bool = Query(False, description="Якщо true - ігнорує пагінацію і тягне ВСЕ (обережно!)")
):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase unavailable")

    collection = resolve_collection(table)

    try:
        # 1. Формуємо фільтр
        # Пріоритет: filter_raw > filters
        active_filter = ""
        if filter_raw:
            active_filter = filter_raw
        elif filters:
            active_filter = build_filter_expr(filters)

        # 2. Опції запиту
        query_options = {}
        if sort: query_options["sort"] = sort
        if expand: query_options["expand"] = expand
        if active_filter: query_options["filter"] = active_filter

        # 3. Виконання запиту
        if full_list:
            # Тягнемо все (стара логіка)
            records = client.collection(collection).get_full_list(query_params=query_options)
            return [sanitize_record(r) for r in records]
        else:
            # Пагінація (нова логіка)
            result = client.collection(collection).get_list(page, perPage, query_params=query_options)
            
            return {
                "items": [sanitize_record(r) for r in result.items],
                "page": result.page,
                "perPage": result.per_page,
                "totalItems": result.total_items,
                "totalPages": result.total_pages
            }

    except Exception as e:
        # Логування можна додати тут
        raise HTTPException(status_code=500, detail=f"PB Error: {str(e)}")


# ───────────────────────────────
# ➕ POST /api/pb/<table> - СТВОРЕННЯ
# ───────────────────────────────
@router.post("/pb/{table}")
def pb_create(table: str, payload: CRUDPayload):
    client = db.get_client()
    if not client: raise HTTPException(status_code=500)
    
    collection = resolve_collection(table)
    try:
        record = client.collection(collection).create(payload.data)
        return sanitize_record(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# ✏️ PATCH /api/pb/<table>/<id> - ОНОВЛЕННЯ
# ───────────────────────────────
@router.patch("/pb/{table}/{record_id}")
def pb_update(table: str, record_id: str, payload: CRUDPayload):
    client = db.get_client()
    if not client: raise HTTPException(status_code=500)

    collection = resolve_collection(table)
    try:
        record = client.collection(collection).update(record_id, payload.data)
        return sanitize_record(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# 🗑 DELETE /api/pb/<table>/<id> - ВИДАЛЕННЯ
# ───────────────────────────────
@router.delete("/pb/{table}/{record_id}")
def pb_delete(table: str, record_id: str):
    client = db.get_client()
    if not client: raise HTTPException(status_code=500)

    collection = resolve_collection(table)
    try:
        client.collection(collection).delete(record_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────
# 📂 POST /api/pb/<table>/<id>/file - ЗАВАНТАЖЕННЯ ФАЙЛУ
# ───────────────────────────────
@router.post("/pb/{table}/{record_id}/file")
async def pb_upload_file(
    table: str, 
    record_id: str, 
    field: str = Form(..., description="Назва поля в базі (напр. 'avatar')"),
    file: UploadFile = File(...)
):
    """
    Універсальний завантажувач файлів.
    1. Створіть запис через звичайний POST.
    2. Отримайте ID.
    3. Викличте цей метод, щоб додати файл у конкретне поле.
    """
    client = db.get_client()
    if not client: raise HTTPException(status_code=500)

    collection = resolve_collection(table)

    try:
        # Читаємо файл у байти
        file_content = await file.read()
        
        # PocketBase очікує (filename, content)
        files_payload = {
            field: (file.filename, file_content)
        }

        # Оновлюємо запис, додаючи файл
        record = client.collection(collection).update(record_id, {}, files=files_payload)
        return sanitize_record(record)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
