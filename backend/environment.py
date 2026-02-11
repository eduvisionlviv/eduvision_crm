import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Основні налаштування проекту ---
    PROJECT_NAME: str = "Eduvision CRM"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # --- Змінні PocketBase (беруться з Coolify / Docker env) ---
    PB_URL: str | None = os.getenv("PB_URL")
    PB_ADMIN_EMAIL: str | None = os.getenv("PB_ADMIN_EMAIL")
    PB_ADMIN_PASSWORD: str | None = os.getenv("PB_ADMIN_PASSWORD")

    class Config:
        case_sensitive = True


settings = Settings()
