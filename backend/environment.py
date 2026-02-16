import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Eduvision CRM"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Appwrite connection
    APPWRITE_ENDPOINT: str | None = os.getenv("APPWRITE_ENDPOINT")
    APPWRITE_PROJECT_ID: str | None = os.getenv("APPWRITE_PROJECT_ID")
    APPWRITE_API_KEY: str | None = os.getenv("APPWRITE_API_KEY")
    APPWRITE_DATABASE_ID: str | None = os.getenv("APPWRITE_DATABASE_ID")

    # Optional mapping for logical table name -> Appwrite collection ID
    # Format: "lc:learning_centers,user_staff:staff"
    APPWRITE_COLLECTION_MAP_RAW: str = os.getenv("APPWRITE_COLLECTION_MAP", "")

    # Optional storage integration for file upload endpoint
    APPWRITE_STORAGE_BUCKET_ID: str | None = os.getenv("APPWRITE_STORAGE_BUCKET_ID")
    APPWRITE_MAX_UPLOAD_BYTES: int = int(os.getenv("APPWRITE_MAX_UPLOAD_BYTES", "5242880"))  # 5MB

    @property
    def APPWRITE_COLLECTION_MAP(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        raw = self.APPWRITE_COLLECTION_MAP_RAW.strip()
        if not raw:
            return mapping

        for pair in raw.split(","):
            if ":" not in pair:
                continue
            key, value = pair.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                mapping[key] = value
        return mapping

    class Config:
        case_sensitive = True


settings = Settings()
