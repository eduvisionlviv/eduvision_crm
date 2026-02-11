from pocketbase import PocketBase
from backend.environment import settings

class Database:
    def __init__(self):
        self.client = PocketBase(settings.PB_URL)
        self.is_authenticated = False

    def connect(self):
        try:
            # Спроба авторизації
            self.client.admins.auth_with_password(
                settings.PB_ADMIN_EMAIL, 
                settings.PB_ADMIN_PASSWORD
            )
            
            # ПРАВИЛЬНО: статус перевіряємо через auth_store
            self.is_authenticated = self.client.auth_store.is_valid
            
            if self.is_authenticated:
                print(f"✅ Успішно підключено до PocketBase: {settings.PB_URL}")
        except Exception as e:
            print(f"❌ Помилка підключення до PocketBase: {e}")
            self.is_authenticated = False

    def get_client(self) -> PocketBase:
        if not self.is_authenticated:
            self.connect()
        return self.client

db = Database()
