import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Eduvision CRM"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Teable connection
    TEABLE_BASE_URL: str = os.getenv("TEABLE_BASE_URL", "https://app.teable.ai")
    TEABLE_API_TOKEN: str | None = os.getenv("TEABLE_API_TOKEN")
    TEABLE_TIMEOUT_SECONDS: float = float(os.getenv("TEABLE_TIMEOUT_SECONDS", "20"))

    # Optional mapping for logical table name -> Teable table ID
    # Format: "lc:tblXXXX,user_staff:tblYYYY"
    TEABLE_TABLE_MAP_RAW: str = os.getenv("TEABLE_TABLE_MAP", "")

    # Upload limits for /file endpoint (currently placeholder integration)
    TEABLE_MAX_UPLOAD_BYTES: int = int(os.getenv("TEABLE_MAX_UPLOAD_BYTES", "5242880"))  # 5MB

    @property
    def TEABLE_TABLE_MAP(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        raw = self.TEABLE_TABLE_MAP_RAW.strip()
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
