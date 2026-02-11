import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Основні налаштування проекту ---
    PROJECT_NAME: str = "Eduvision CRM"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # --- Змінні PocketBase (беруться з Coolify) ---
    PB_URL: str = os.getenv("PB_URL")
    PB_ADMIN_EMAIL: str = os.getenv("PB_ADMIN_EMAIL")
    PB_ADMIN_PASSWORD: str = os.getenv("PB_ADMIN_PASSWORD")

    # Тут у майбутньому можна додавати інші змінні:
    # TG_BOT_TOKEN: str = os.getenv("TG_BOT_TOKEN")
    # EMAIL_SENDER: str = os.getenv("EMAIL_SENDER")

    class Config:
        case_sensitive = True

# Створюємо об'єкт, який будемо імпортувати в інші файли
settings = Settings()
