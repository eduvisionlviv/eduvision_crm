# backend/api/universal_api.py
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.pocketbase import db

router = APIRouter(prefix="/api", tags=["pb-universal"])

# ───────────────────────────────
# 🔖 Реєстр відомих таблиць
# ───────────────────────────────
# Ключ – «логічна» назва в API, значення – реальна PocketBase collection
KNOWN_TABLES: Dict[str, str] = {
    "user_staff": "user_staff",
    "reg": "reg",
    # сюди потім додаватимеш:
    # "courses": "courses",
    # "centers": "centers",
}


class CRUDPayload(BaseModel):
    data: Dict[str, Any]


# ───────────────────────────────
# 🧩 Допоміжне
# ───────────────────────────────
def resolve_collection(table: str) -> str:
    """
    Переводить «логічну» назву в реальну колекцію PocketBase.
    Якщо немає в KNOWN_TABLES – 400.
    """
    if table not in KNOWN_TABLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown table '{table}'. "
                f"Додай її у KNOWN_TABLES в universal_api.py."
            ),
        )
    return KNOWN_TABLES[table]


def build_filter_expr(filters: List[str]) -> str:
    """
    filters=col:op:value → PocketBase filter string.
    Підтримує: eq, neq, gt, lt, gte, lte, like, ilike
    """
    exprs: List[str] = []
    for raw in filters:
        parts = raw.split(":", 3)
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail=f"Bad filter: {raw}")
        col, op, val = parts

        if op == "eq":
            exprs.append(f"{col} = '{val}'")
        elif op == "neq":
            exprs.append(f"{col} != '{val}'")
        elif op == "gt":
            exprs.append(f"{col} > '{val}'")
        elif op == "lt":
            exprs.append(f"{col} < '{val}'")
        elif op == "gte":
            exprs.append(f"{col} >= '{val}'")
        elif op == "lte":
            exprs.append(f"{col} <= '{val}'")
        elif op in ("like", "ilike"):
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
    filters: Optional[List[str]] = Query(
        default=None,
        description="Формат: col:op:value, напр. user_mail:eq:test@test.com",
    ),
):
    client = db.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="PocketBase client not available")

    collection = resolve_collection(table)

    try:
        if not filters:
            # get_full_list без фільтрів
            records = client.collection(collection).get_full_list()
            return records

        filter_str = build_filter_expr(filters)
        # фільтр – через get_list
        page_res = client.collection(collection).get_list(
            page=1,
            per_page=500,  # максимум, якщо треба більше – окремо продумати пагінацію
            filter=filter_str,
        )
        items = page_res.items if hasattr(page_res, "items") else []
        return items

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
        return record
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
        return record
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
