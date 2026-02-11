from pocketbase import PocketBase
from backend.environment import settings


class Database:
    def __init__(self):
        print(f"DEBUG: Спроба підключення до URL: '{settings.PB_URL}'")
        self.client = PocketBase(settings.PB_URL) if settings.PB_URL else None
        self.is_authenticated = False

    def connect(self):
        if not self.client:
            print("⚠️ PB_URL не заданий, пропускаємо підключення до PocketBase")
            self.is_authenticated = False
            return

        try:
            self.client.admins.auth_with_password(
                settings.PB_ADMIN_EMAIL,
                settings.PB_ADMIN_PASSWORD,
            )

            # ВАЖЛИВО: правильно перевіряємо авторизацію
            self.is_authenticated = self.client.auth_store.model is not None

            if self.is_authenticated:
                print(f"✅ Успішно підключено до PocketBase: {settings.PB_URL}")
            else:
                print("⚠️ Авторизація в PocketBase невалідна, але API працює")
        except Exception as e:
            print(f"❌ Помилка підключення до PocketBase: {e}")
            self.is_authenticated = False

    def get_client(self) -> PocketBase | None:
        if not self.is_authenticated:
            self.connect()
        return self.client


db = Database()
