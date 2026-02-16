from typing import Any, Dict, List, Literal, Optional, Type

from appwrite.query import Query
from fastapi import APIRouter, File, Form, HTTPException, Query as FastQuery, UploadFile
from pydantic import BaseModel, Field

from backend.environment import settings
from backend.services.appwrite import db

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

# Зберігаємо префікс /pb для зворотної сумісності фронтенду,
# але фактично працюємо через Appwrite.
router = APIRouter(prefix="/api", tags=["appwrite-universal"])

TABLE_SCHEMAS: Dict[str, Type[BaseSchema]] = {
    "lc": LCSchema,
    "user_staff": StaffSchema,
    "reg": RegSchema,
    "courses": CourseSchema,
    "rooms": RoomSchema,
    "sources": SourceSchema,
    "new_table_name": NewTableSchema,
}

# Технічні поля, які часто потрібні для сорту/фільтру
BASE_QUERY_FIELDS = {"id", "created", "updated"}


class CRUDPayload(BaseModel):
    data: Dict[str, Any]


class TableAttributePayload(BaseModel):
    key: str
    type: Literal[
        "string",
        "varchar",
        "text",
        "mediumtext",
        "longtext",
        "integer",
        "float",
        "boolean",
        "datetime",
        "email",
        "url",
        "enum",
    ]
    required: bool = False
    array: bool = False
    default: Any = None
    size: Optional[int] = None
    min: Optional[float] = None
    max: Optional[float] = None
    elements: Optional[List[str]] = None
    encrypt: bool = False


class TableIndexPayload(BaseModel):
    key: str
    type: Literal["key", "fulltext", "unique", "spatial"] = "key"
    attributes: List[str] = Field(default_factory=list)
    orders: Optional[List[Literal["asc", "desc"]]] = None
    lengths: Optional[List[int]] = None


class CreateTablePayload(BaseModel):
    table_id: str
    name: str
    permissions: List[str] = Field(default_factory=list)
    document_security: bool = False
    enabled: bool = True
    attributes: List[TableAttributePayload] = Field(default_factory=list)
    indexes: List[TableIndexPayload] = Field(default_factory=list)


def ensure_schema_mutations_allowed() -> None:
    if not settings.APPWRITE_ALLOW_SCHEMA_MUTATIONS:
        raise HTTPException(
            status_code=403,
            detail=(
                "Schema mutations are disabled. "
                "Set APPWRITE_ALLOW_SCHEMA_MUTATIONS=true to allow creating tables."
            ),
        )


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


def build_query_filters(filters: List[str], allowed_fields: set[str]) -> List[str]:
    """Parse filters in format field:op:value to Appwrite queries."""
    queries: List[str] = []

    for raw in filters:
        parts = raw.split(":", 2)
        if len(parts) < 3:
            continue

        field, op, raw_value = parts

        if field not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Filtering by '{field}' is not allowed")

        parsed_value = parse_scalar(raw_value)

        if op == "eq":
            queries.append(Query.equal(field, [parsed_value]))
        elif op == "neq":
            queries.append(Query.not_equal(field, parsed_value))
        elif op == "gt":
            queries.append(Query.greater_than(field, parsed_value))
        elif op == "lt":
            queries.append(Query.less_than(field, parsed_value))
        elif op == "gte":
            queries.append(Query.greater_than_equal(field, parsed_value))
        elif op == "lte":
            queries.append(Query.less_than_equal(field, parsed_value))
        elif op in ("like", "ilike"):
            queries.append(Query.search(field, str(parsed_value)))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported filter operation '{op}'")

    return queries


def validate_sort(sort: Optional[str], allowed_fields: set[str]) -> Optional[str]:
    if not sort:
        return None

    sort_field = sort[1:] if sort.startswith("-") else sort
    if sort_field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Sorting by '{sort_field}' is not allowed")
    return sort


@router.get("/appwrite/tables")
def appwrite_list_tables():
    ensure_schema_mutations_allowed()
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

    try:
        return db.list_tables()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")


@router.post("/appwrite/tables")
def appwrite_create_table(payload: CreateTablePayload):
    ensure_schema_mutations_allowed()
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

    try:
        collection = db.create_table(
            table_id=payload.table_id,
            name=payload.name,
            permissions=payload.permissions,
            document_security=payload.document_security,
            enabled=payload.enabled,
        )

        created_attributes = []
        for attr in payload.attributes:
            created_attributes.append(db.create_table_attribute(payload.table_id, attr.model_dump()))

        created_indexes = []
        for index in payload.indexes:
            created_indexes.append(db.create_table_index(payload.table_id, index.model_dump()))

        return {
            "status": "ok",
            "collection": collection,
            "attributes": created_attributes,
            "indexes": created_indexes,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create table: {str(e)}")


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
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

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
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

    schema_class = resolve_schema(table)

    try:
        record = db.create_record(table, payload.data)
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/pb/{table}/{record_id}")
def pb_update(table: str, record_id: str, payload: CRUDPayload):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

    schema_class = resolve_schema(table)

    try:
        record = db.update_record(table, record_id, payload.data)
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pb/{table}/{record_id}")
def pb_delete(table: str, record_id: str):
    if not db.get_client():
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

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
        raise HTTPException(status_code=503, detail="Appwrite service unavailable")

    schema_class = resolve_schema(table)

    if not settings.APPWRITE_STORAGE_BUCKET_ID:
        raise HTTPException(
            status_code=501,
            detail="File upload requires APPWRITE_STORAGE_BUCKET_ID configuration",
        )

    allowed_fields = allowed_query_fields(schema_class)
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"File field '{field}' is not allowed")

    content = await file.read()
    if len(content) > settings.APPWRITE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed is {settings.APPWRITE_MAX_UPLOAD_BYTES} bytes",
        )

    try:
        uploaded = db.upload_file(file.filename or "upload.bin", content)

        # Link file id to document field. Appwrite schema should allow this field.
        record = db.update_record(table, record_id, {field: uploaded.get("$id")})
        return schema_class.model_validate(record).model_dump(by_alias=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
