# backend/api/universal_api.py
import json
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Request
from pydantic import BaseModel

from backend.services.pocketbase import db

# Імпортуємо всі схеми з schemas.py
from .schemas import (
    LCSchema, 
    StaffSchema, 
    RegSchema, 
    CourseSchema, 
    RoomSchema, 
    SourceSchema,
    NewTableSchema, # <--- Якщо ви не використовуєте цю таблицю, закоментуйте або видаліть
    BaseSchema
)

router = APIRouter(prefix="/api", tags=["pb-universal"])

# ───────────────────────────────
# 🔖 Реєстр схем (Whitelist & Mapping)
# ───────────────────────────────
# Ключ = назва таблиці в URL та PocketBase
# Значення = Pydantic клас для валідації та мапінгу
TABLE_SCHEMAS: Dict[str, Type[BaseSchema]] = {
    "lc": LCSchema,
    "user_staff": StaffSchema,
    "reg": RegSchema,
    "courses": CourseSchema,
    "rooms": RoomSchema,
    "sources": SourceSchema,
    
    # 👇 Впишіть сюди реальну назву таблиці з PocketBase (якщо використовуєте)
    "new_table_name": NewTableSchema, 
}

class CRUDPayload(BaseModel):
    data: Dict[str, Any]

# ───────────────────────────────
# 🧩 Допоміжні функції
# ───────────────────────────────

def resolve_schema(table: str) -> Type[BaseSchema]:
    """Перевіряє, чи дозволена таблиця, і повертає її схему."""
    if table not in TABLE_SCHEMAS:
        raise HTTPException(
            status_code=403,
            detail=f"Access to table '{table}' is restricted or schema not defined."
        )
    return TABLE_SCHEMAS[table]

def build_filter_expr(filters: List[str]) -> str:
    """
    Конвертує прості фільтри format=col:op:val у PocketBase синтаксис.
    Підтримує: eq, neq, gt, lt, gte, lte, like.
    Приклад: filters=lc_id:eq:123 -> lc_id = '123'
    """
    exprs: List[str] = []
    for raw in filters:
        parts = raw.split(":", 2) # Розбиваємо максимум на 3 частини (col, op, val)
        if len(parts) < 3:
            continue
        
        col, op, val = parts[0], parts[1], parts[2]

        # Базова санітизація значень
        if val.lower() in ["true", "false", "null"]:
            safe_val = val.lower()
        elif val.replace(".", "", 1).isdigit():
            safe_val = val
        else:
            # Екранування одинарних лапок для безпеки PB
            safe_val = f"'{val.replace("'", "\\'")}'"

        if op == "eq": exprs.append(f"{col} = {safe_val}")
        elif op == "neq": exprs.append(f"{col} != {safe_val}")
        elif op == "gt": exprs.append(f"{col} > {safe_val}")
        elif op == "lt": exprs.append(f"{col} < {safe_val}")
        elif op == "gte": exprs.append(f"{col} >= {safe_val}")
        elif op == "lte": exprs.append(f"{col} <= {safe_val}")
        elif op in ("like", "ilike"): exprs.append(f"{col} ~ {safe_val}")

    return " && ".join(exprs)

# ───────────────────────────────
# 🔍 GET /api/pb/<table> - УНІВЕРСАЛЬНИЙ ПОШУК
# ───────────────────────────────
@router.get("/pb/{table}")
def pb_get(
    table: str,
    request: Request,
    page: int = Query(1, ge=1),
    # ✅ ВИПРАВЛЕНО: Збільшено ліміт до 25000 для експорту великих даних
    perPage: int = Query(50, ge=1, le=25000),
    sort: Optional[str] = Query(None),
    expand: Optional[str] = Query(None),
    filters: Optional[List[str]] = Query(None, alias="filters"), # Підтримка ?filters=...
    filter_raw: Optional[str] = Query(None, alias="filter"),     # Підтримка ?filter=... (стандарт PB)
    full_list: bool = Query(False)
):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=503, detail="PocketBase service unavailable")

    # 1. Отримуємо схему (і перевіряємо доступ)
    schema_class = resolve_schema(table)

    try:
        # 2. Формуємо параметри запиту до PB
        query_options = {}
        if sort: query_options["sort"] = sort
        if expand: query_options["expand"] = expand
        
        # Пріоритет: filter (raw SQL-like) > filters (simple helper)
        active_filter = ""
        if filter_raw:
            active_filter = filter_raw
        elif filters:
            active_filter = build_filter_expr(filters)
        
        if active_filter:
            query_options["filter"] = active_filter

        # 3. Виконуємо запит до бази
        raw_items = []
        meta = {}

        if full_list:
            # Обережно з цим на великих таблицях, але ліміт 25000 дозволяє викачувати багато
            raw_items = client.collection(table).get_full_list(query_params=query_options)
            meta = {
                "page": 1,
                "perPage": len(raw_items),
                "totalItems": len(raw_items),
                "totalPages": 1
            }
        else:
            result = client.collection(table).get_list(page, perPage, query_params=query_options)
            raw_items = result.items
            meta = {
                "page": result.page,
                "perPage": result.per_page,
                "totalItems": result.total_items,
                "totalPages": result.total_pages
            }

        # 4. 🔥 НОРМАЛІЗАЦІЯ ДАНИХ ЧЕРЕЗ PYDANTIC 🔥
        clean_items = []
        for item in raw_items:
            # Pydantic читає з атрибутів об'єкта PB
            validated_obj = schema_class.model_validate(item)
            # Вивантажуємо в dict, використовуючи "чисті" імена (by_alias=False)
            clean_items.append(validated_obj.model_dump(by_alias=False))

        return {
            **meta,
            "items": clean_items
        }

    except Exception as e:
        print(f"PB API Error ({table}): {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ───────────────────────────────
# ➕ POST /api/pb/<table> - СТВОРЕННЯ
# ───────────────────────────────
@router.post("/pb/{table}")
def pb_create(table: str, payload: CRUDPayload):
    client = db.get_client()
    if not client: raise HTTPException(status_code=503)
    
    schema_class = resolve_schema(table)
    
    try:
        # При створенні запису передаємо дані як є
        record = client.collection(table).create(payload.data)
        
        # Повертаємо вже чистий об'єкт
        validated = schema_class.model_validate(record)
        return validated.model_dump(by_alias=False)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ───────────────────────────────
# ✏️ PATCH /api/pb/<table>/<id> - ОНОВЛЕННЯ
# ───────────────────────────────
@router.patch("/pb/{table}/{record_id}")
def pb_update(table: str, record_id: str, payload: CRUDPayload):
    client = db.get_client()
    if not client: raise HTTPException(status_code=503)

    schema_class = resolve_schema(table)
    
    try:
        record = client.collection(table).update(record_id, payload.data)
        
        validated = schema_class.model_validate(record)
        return validated.model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ───────────────────────────────
# 🗑 DELETE /api/pb/<table>/<id> - ВИДАЛЕННЯ
# ───────────────────────────────
@router.delete("/pb/{table}/{record_id}")
def pb_delete(table: str, record_id: str):
    client = db.get_client()
    if not client: raise HTTPException(status_code=503)

    resolve_schema(table) # Перевірка доступу

    try:
        client.collection(table).delete(record_id)
        return {"status": "ok", "id": record_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ───────────────────────────────
# 📂 FILE UPLOAD
# ───────────────────────────────
@router.post("/pb/{table}/{record_id}/file")
async def pb_upload_file(
    table: str, 
    record_id: str, 
    field: str = Form(...),
    file: UploadFile = File(...)
):
    client = db.get_client()
    if not client: raise HTTPException(status_code=503)

    schema_class = resolve_schema(table)

    try:
        # ✅ ВИПРАВЛЕНО: Не читаємо весь файл у RAM (await file.read()).
        # Передаємо file.file (це потік), щоб уникнути переповнення пам'яті.
        files_payload = { field: (file.filename, file.file) }

        record = client.collection(table).update(record_id, {}, files=files_payload)
        
        validated = schema_class.model_validate(record)
        return validated.model_dump(by_alias=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
