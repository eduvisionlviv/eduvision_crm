from __future__ import annotations

from typing import Any, Dict, List, Optional

from appwrite.client import Client
from appwrite.enums.index_type import IndexType
from appwrite.enums.order_by import OrderBy
from appwrite.input_file import InputFile
from appwrite.query import Query
from appwrite.services.databases import Databases
from appwrite.services.storage import Storage

from backend.environment import settings


class AppwriteDB:
    """Thin wrapper around Appwrite Databases + optional Storage services."""

    def __init__(self) -> None:
        self.client: Optional[Client] = None
        self.databases: Optional[Databases] = None
        self.storage: Optional[Storage] = None
        self.is_authenticated: bool = False
        self.database_id: Optional[str] = settings.APPWRITE_DATABASE_ID
        self.bucket_id: Optional[str] = settings.APPWRITE_STORAGE_BUCKET_ID

    def connect(self) -> None:
        endpoint = settings.APPWRITE_ENDPOINT
        project_id = settings.APPWRITE_PROJECT_ID
        api_key = settings.APPWRITE_API_KEY

        if not endpoint or not project_id or not api_key or not self.database_id:
            self.is_authenticated = False
            return

        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project_id)
        client.set_key(api_key)

        self.client = client
        self.databases = Databases(client)
        self.storage = Storage(client)

        # smoke check
        self.databases.list()
        self.is_authenticated = True

    def get_client(self) -> Optional[Databases]:
        return self.databases

    def _require_service(self) -> Databases:
        if not self.databases or not self.database_id:
            raise RuntimeError("Appwrite Databases client not initialized")
        return self.databases

    def _require_storage(self) -> Storage:
        if not self.storage or not self.bucket_id:
            raise RuntimeError("Appwrite Storage client/bucket not initialized")
        return self.storage

    def resolve_collection_id(self, table: str) -> str:
        return settings.APPWRITE_COLLECTION_MAP.get(table, table)

    @staticmethod
    def _normalize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(doc)
        if "$id" in normalized and "id" not in normalized:
            normalized["id"] = normalized["$id"]
        if "$createdAt" in normalized and "created" not in normalized:
            normalized["created"] = normalized["$createdAt"]
        if "$updatedAt" in normalized and "updated" not in normalized:
            normalized["updated"] = normalized["$updatedAt"]
        return normalized

    def list_tables(self) -> Dict[str, Any]:
        db = self._require_service()
        return db.list_collections(self.database_id)

    def create_table(
        self,
        table_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        document_security: bool = False,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        db = self._require_service()
        return db.create_collection(
            database_id=self.database_id,
            collection_id=table_id,
            name=name,
            permissions=permissions or [],
            document_security=document_security,
            enabled=enabled,
        )

    def create_table_attribute(self, table_id: str, attr: Dict[str, Any]) -> Dict[str, Any]:
        db = self._require_service()
        attr_type = attr["type"]
        key = attr["key"]
        required = attr.get("required", False)
        array = attr.get("array", False)

        if attr_type == "string":
            return db.create_string_attribute(
                self.database_id,
                table_id,
                key,
                attr.get("size", 255),
                required,
                default=attr.get("default"),
                array=array,
                encrypt=attr.get("encrypt", False),
            )
        if attr_type == "varchar":
            return db.create_varchar_attribute(
                self.database_id,
                table_id,
                key,
                attr.get("size", 255),
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "text":
            return db.create_text_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "mediumtext":
            return db.create_mediumtext_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "longtext":
            return db.create_longtext_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "integer":
            return db.create_integer_attribute(
                self.database_id,
                table_id,
                key,
                required,
                min=attr.get("min"),
                max=attr.get("max"),
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "float":
            return db.create_float_attribute(
                self.database_id,
                table_id,
                key,
                required,
                min=attr.get("min"),
                max=attr.get("max"),
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "boolean":
            return db.create_boolean_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "datetime":
            return db.create_datetime_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "email":
            return db.create_email_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "url":
            return db.create_url_attribute(
                self.database_id,
                table_id,
                key,
                required,
                default=attr.get("default"),
                array=array,
            )
        if attr_type == "enum":
            return db.create_enum_attribute(
                self.database_id,
                table_id,
                key,
                attr.get("elements", []),
                required,
                default=attr.get("default"),
                array=array,
            )

        raise ValueError(f"Unsupported attribute type '{attr_type}'")

    def create_table_index(self, table_id: str, index: Dict[str, Any]) -> Dict[str, Any]:
        db = self._require_service()

        index_type_raw = index["type"]
        index_type = IndexType(index_type_raw)

        orders_raw = index.get("orders")
        orders = [OrderBy(order) for order in orders_raw] if orders_raw else None

        return db.create_index(
            database_id=self.database_id,
            collection_id=table_id,
            key=index["key"],
            type=index_type,
            attributes=index["attributes"],
            orders=orders,
            lengths=index.get("lengths"),
        )

    def list_records(
        self,
        table: str,
        page: int,
        per_page: int,
        sort: Optional[str] = None,
        filters: Optional[List[str]] = None,
        full_list: bool = False,
    ) -> Dict[str, Any]:
        db = self._require_service()
        collection_id = self.resolve_collection_id(table)

        base_queries = list(filters or [])
        if sort:
            if sort.startswith("-"):
                base_queries.append(Query.order_desc(sort[1:]))
            else:
                base_queries.append(Query.order_asc(sort))

        if full_list:
            offset = 0
            batch_limit = min(max(per_page, 1), 100)
            all_docs: List[Dict[str, Any]] = []

            while True:
                page_queries = [*base_queries, Query.limit(batch_limit), Query.offset(offset)]
                res = db.list_documents(self.database_id, collection_id, page_queries)
                docs = res.get("documents", [])
                all_docs.extend(self._normalize_document(doc) for doc in docs)
                if len(docs) < batch_limit:
                    break
                offset += batch_limit

            total = len(all_docs)
            return {
                "page": 1,
                "perPage": total,
                "totalItems": total,
                "totalPages": 1,
                "items": all_docs,
            }

        offset = (page - 1) * per_page
        queries = [*base_queries, Query.limit(per_page), Query.offset(offset)]
        res = db.list_documents(self.database_id, collection_id, queries)
        total_items = res.get("total", 0)
        total_pages = (total_items + per_page - 1) // per_page if per_page else 1

        return {
            "page": page,
            "perPage": per_page,
            "totalItems": total_items,
            "totalPages": total_pages,
            "items": [self._normalize_document(doc) for doc in res.get("documents", [])],
        }

    def create_record(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        db = self._require_service()
        collection_id = self.resolve_collection_id(table)
        created = db.create_document(self.database_id, collection_id, "unique()", data)
        return self._normalize_document(created)

    def update_record(self, table: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        db = self._require_service()
        collection_id = self.resolve_collection_id(table)
        updated = db.update_document(self.database_id, collection_id, record_id, data)
        return self._normalize_document(updated)

    def delete_record(self, table: str, record_id: str) -> None:
        db = self._require_service()
        collection_id = self.resolve_collection_id(table)
        db.delete_document(self.database_id, collection_id, record_id)

    def upload_file(self, filename: str, raw_data: bytes) -> Dict[str, Any]:
        storage = self._require_storage()
        appwrite_file = InputFile.from_bytes(raw_data, filename)
        return storage.create_file(self.bucket_id, "unique()", appwrite_file)


# Global singleton used by API routers
# Mirrors old import style: from backend.services.appwrite import db
db = AppwriteDB()
