from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, File, Form, HTTPException, Query as FastQuery, UploadFile
from pydantic import BaseModel

from backend.environment import settings
from backend.services.teable import db

from .schemas import (
    BaseSchema,
    CourseSchema,
    LCSchema,
    NewTableSchema,
    RegSchema,
    RoomSchema,
    SourceSchema,
    StaffSchema,
)

# Зберігаємо префікс /pb для зворотної сумісності фронтенду.
router = APIRouter(prefix="/api", tags=["teable-universal"])

TABLE_SCHEMAS: Dict[str, Type[BaseSchema]] = {
    "lc": LCSchema,
    "user_staff": StaffSchema,
    "reg": RegSchema,
    "courses": CourseSchema,
    "rooms": RoomSchema,
    "sources": SourceSchema,
    "new_table_name": NewTableSchema,
}

BASE_QUERY_FIELDS = {"id", "created", "updated"}


class CRUDPayload(BaseModel):
    data: Dict[str, Any]


def resolve_schema(table: str) -> Type[BaseSchema]:
    if table not in TABLE_SCHEMAS:
        raise HTTPException(
            status_code=403,
            detail=f"Access to table '{table}' is restricted or schema not defined.",
        )
    return TABLE_SCHEMAS[table]


def allowed_query_fields(schema_class: Type[BaseSchema]) -> set[str]:
    fields = set(BASE_QUERY_FIELDS)
    for name, field_info in schema_class.model_fields.items():
        fields.add(name)
        if field_info.alias:
            fields.add(field_info.alias)
    return fields


def parse_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "null":
        return None

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def build_query_filters(filters: List[str], allowed_fields: set[str]) -> List[Dict[str, Any]]:
    """Parse filters in format field:op:value into internal filter dicts."""
    query_filters: List[Dict[str, Any]] = []

    for raw in filters:
        parts = raw.split(":", 2)
        if len(parts) < 3:
            continue

        field, op, raw_value = parts

        if field not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Filtering by '{field}' is not allowed")

        if op not in {"eq", "neq", "gt", "lt", "gte", "lte", "like", "ilike"}:
            raise HTTPException(status_code=400, detail=f"Unsupported filter operation '{op}'")

        query_filters.append({"field": field, "op": op, "value": parse_scalar(raw_value)})

    return query_filters


def validate_sort(sort: Optional[str], allowed_fields: set[str]) -> Optional[str]:
    if not sort:
        return None

    sort_field = sort[1:] if sort.startswith("-") else sort
    if sort_field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Sorting by '{sort_field}' is not allowed")
    return sort


@router.get("/pb/{table}")
def pb_get(
    table: str,
    page: int = FastQuery(1, ge=1),
    perPage: int = FastQuery(50, ge=1, le=25000),
    sort: Optional[str] = FastQuery(None),
    filters: Optional[List[str]] = FastQuery(None, alias="filters"),
    full_list: bool = FastQuery(False),
):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Teable service unavailable")

    schema_class = resolve_schema(table)
    allowed_fields = allowed_query_fields(schema_class)

    try:
        safe_sort = validate_sort(sort, allowed_fields)
        query_filters = build_query_filters(filters or [], allowed_fields)

        result = db.list_records(
            table=table,
            page=page,
            per_page=perPage,
            sort=safe_sort,
            filters=query_filters,
            full_list=full_list,
        )

        clean_items = [
            schema_class.model_validate(item).model_dump(by_alias=False)
            for item in result["items"]
        ]

        return {**result, "items": clean_items}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/pb/{table}")
def pb_create(table: str, payload: CRUDPayload):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Teable service unavailable")

    schema_class = resolve_schema(table)

    try:
        record = db.create_record(table, payload.data)
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/pb/{table}/{record_id}")
def pb_update(table: str, record_id: str, payload: CRUDPayload):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Teable service unavailable")

    schema_class = resolve_schema(table)

    try:
        record = db.update_record(table, record_id, payload.data)
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pb/{table}/{record_id}")
def pb_delete(table: str, record_id: str):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Teable service unavailable")

    resolve_schema(table)

    try:
        db.delete_record(table, record_id)
        return {"status": "ok", "id": record_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pb/{table}/{record_id}/file")
async def pb_upload_file(
    table: str,
    record_id: str,
    field: str = Form(...),
    file: UploadFile = File(...),
):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Teable service unavailable")

    schema_class = resolve_schema(table)
    allowed_fields = allowed_query_fields(schema_class)
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"File field '{field}' is not allowed")

    content = await file.read()
    if len(content) > settings.TEABLE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed is {settings.TEABLE_MAX_UPLOAD_BYTES} bytes",
        )

    try:
        uploaded = db.upload_file(file.filename or "upload.bin", content)
        record = db.update_record(table, record_id, {field: uploaded.get("url") or uploaded.get("token")})
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Upload integration pending: {str(e)}")
