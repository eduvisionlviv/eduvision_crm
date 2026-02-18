from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from backend.environment import settings


class TeableDB:
    """Thin wrapper around Teable REST API."""

    def __init__(self) -> None:
        self.base_url: Optional[str] = settings.TEABLE_BASE_URL
        self.token: Optional[str] = settings.TEABLE_API_TOKEN
        self.is_authenticated: bool = False

    def connect(self) -> None:
        self.base_url = settings.TEABLE_BASE_URL
        self.token = settings.TEABLE_API_TOKEN

        if not self.base_url or not self.token:
            self.is_authenticated = False
            return

        # smoke check
        self._request("GET", "/api/auth/user")
        self.is_authenticated = True

    def get_client(self) -> Optional["TeableDB"]:
        return self if self.is_authenticated else None

    def resolve_table_id(self, table: str) -> str:
        return settings.TEABLE_TABLE_MAP.get(table, table)

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("Teable API token is not configured")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Teable base URL is not configured")

        url = f"{self.base_url.rstrip('/')}{path}"
        with httpx.Client(timeout=settings.TEABLE_TIMEOUT_SECONDS) as client:
            response = client.request(method, url, headers=self._headers(), params=params, json=json)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    @staticmethod
    def _record_to_flat(record: Dict[str, Any]) -> Dict[str, Any]:
        if "fields" in record and isinstance(record["fields"], dict):
            normalized = dict(record["fields"])
            normalized["id"] = record.get("id") or record.get("recordId")
            normalized["created"] = record.get("createdTime") or record.get("created") or ""
            normalized["updated"] = record.get("lastModifiedTime") or record.get("updated") or ""
            return normalized

        normalized = dict(record)
        if "id" not in normalized and "recordId" in normalized:
            normalized["id"] = normalized.get("recordId")
        normalized.setdefault("created", normalized.get("createdTime", ""))
        normalized.setdefault("updated", normalized.get("lastModifiedTime", ""))
        return normalized

    @staticmethod
    def _extract_records(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        for key in ("records", "items", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if isinstance(payload.get("data"), dict):
            data = payload["data"]
            for key in ("records", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    @staticmethod
    def _extract_total(payload: Dict[str, Any], fallback: int) -> int:
        for key in ("total", "totalItems", "count"):
            if isinstance(payload.get(key), int):
                return payload[key]
        if isinstance(payload.get("data"), dict):
            data = payload["data"]
            for key in ("total", "totalItems", "count"):
                if isinstance(data.get(key), int):
                    return data[key]
        return fallback

    @staticmethod
    def _apply_filters(records: List[Dict[str, Any]], filters: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if not filters:
            return records

        def matches(record: Dict[str, Any], f: Dict[str, Any]) -> bool:
            value = record.get(f["field"])
            target = f["value"]
            op = f["op"]

            if op == "eq":
                return value == target
            if op == "neq":
                return value != target
            if op == "gt":
                return value is not None and value > target
            if op == "lt":
                return value is not None and value < target
            if op == "gte":
                return value is not None and value >= target
            if op == "lte":
                return value is not None and value <= target
            if op in ("like", "ilike"):
                if value is None:
                    return False
                value_s = str(value)
                target_s = str(target)
                return target_s.lower() in value_s.lower() if op == "ilike" else target_s in value_s
            return True

        filtered = records
        for item in filters:
            filtered = [row for row in filtered if matches(row, item)]
        return filtered

    @staticmethod
    def _apply_sort(records: List[Dict[str, Any]], sort: Optional[str]) -> List[Dict[str, Any]]:
        if not sort:
            return records
        reverse = sort.startswith("-")
        field = sort[1:] if reverse else sort
        return sorted(records, key=lambda x: (x.get(field) is None, x.get(field)), reverse=reverse)

    def list_records(
        self,
        table: str,
        page: int,
        per_page: int,
        sort: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        full_list: bool = False,
    ) -> Dict[str, Any]:
        table_id = self.resolve_table_id(table)

        if full_list or sort or filters:
            # Teable filter/sort syntax can vary by API version, so we fetch in batches
            # and apply business-level filters/sort locally for API compatibility.
            all_items: List[Dict[str, Any]] = []
            skip = 0
            take = min(max(per_page, 1), 1000)

            while True:
                payload = self._request(
                    "GET",
                    f"/api/table/{table_id}/record",
                    params={"take": take, "skip": skip, "fieldKeyType": "name", "cellFormat": "json"},
                )
                records = self._extract_records(payload)
                normalized_batch = [self._record_to_flat(item) for item in records]
                all_items.extend(normalized_batch)

                if len(records) < take:
                    break
                skip += take

            all_items = self._apply_filters(all_items, filters)
            all_items = self._apply_sort(all_items, sort)

            if full_list:
                return {
                    "page": 1,
                    "perPage": len(all_items),
                    "totalItems": len(all_items),
                    "totalPages": 1,
                    "items": all_items,
                }

            total_items = len(all_items)
            start = (page - 1) * per_page
            end = start + per_page
            paged = all_items[start:end]
            total_pages = (total_items + per_page - 1) // per_page if per_page else 1

            return {
                "page": page,
                "perPage": per_page,
                "totalItems": total_items,
                "totalPages": total_pages,
                "items": paged,
            }

        skip = (page - 1) * per_page
        payload = self._request(
            "GET",
            f"/api/table/{table_id}/record",
            params={"take": per_page, "skip": skip, "fieldKeyType": "name", "cellFormat": "json"},
        )

        records = [self._record_to_flat(item) for item in self._extract_records(payload)]
        total_items = self._extract_total(payload, fallback=len(records))
        total_pages = (total_items + per_page - 1) // per_page if per_page else 1

        return {
            "page": page,
            "perPage": per_page,
            "totalItems": total_items,
            "totalPages": total_pages,
            "items": records,
        }

    def create_record(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        table_id = self.resolve_table_id(table)
        payload = self._request("POST", f"/api/table/{table_id}/record", json={"records": [{"fields": data}]})
        records = self._extract_records(payload)
        if records:
            return self._record_to_flat(records[0])

        # fallback for APIs returning created record directly
        if payload:
            return self._record_to_flat(payload)
        raise RuntimeError("Teable create record returned empty response")

    def update_record(self, table: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        table_id = self.resolve_table_id(table)
        payload = self._request(
            "PATCH",
            f"/api/table/{table_id}/record/{record_id}",
            json={"fields": data},
        )
        return self._record_to_flat(payload)

    def delete_record(self, table: str, record_id: str) -> None:
        table_id = self.resolve_table_id(table)
        # common Teable bulk-delete shape
        self._request("DELETE", f"/api/table/{table_id}/record", json={"recordIds": [record_id]})

    def upload_file(self, filename: str, raw_data: bytes) -> Dict[str, Any]:
        raise RuntimeError(
            "Teable file upload is not configured in this project yet. "
            "Use Teable Upload Attachment API and store returned token/url in the target field."
        )


# Global singleton used by API routers
# import style: from backend.services.teable import db
# NOTE: old Appwrite service has been removed.
db = TeableDB()
