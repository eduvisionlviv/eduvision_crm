from pocketbase import PocketBase
from backend.environment import settings

class Database:
    def __init__(self):
        # Створюємо клієнт PocketBase
        self.client = PocketBase(settings.PB_URL)
        self.is_authenticated = False

    def connect(self):
        """Метод для входу в систему як адміністратор"""
        try:
            # Використовуємо дані з твого нового файлу environment.py
            self.client.admins.auth_with_password(
                settings.PB_ADMIN_EMAIL, 
                settings.PB_ADMIN_PASSWORD
            )
            self.is_authenticated = self.client.admins.is_valid
            if self.is_authenticated:
                print(f"✅ Успішно підключено до PocketBase: {settings.PB_URL}")
        except Exception as e:
            print(f"❌ Помилка підключення до PocketBase: {e}")
            self.is_authenticated = False

    def get_client(self) -> PocketBase:
        """Повертає готовий клієнт для роботи з даними"""
        if not self.is_authenticated:
            self.connect()
        return self.client

# Створюємо один спільний об'єкт бази для всього бекенду
db = Database()
