# Appwrite migration notes

## Статус
- Backend працює через Appwrite Databases (`backend/services/appwrite.py`).
- API-роути лишилися `/api/pb/*` для сумісності фронтенду.
- Старого файлу `backend/services/pocketbase.py` у репозиторії немає.

## Необхідні env
- `APPWRITE_ENDPOINT`
- `APPWRITE_PROJECT_ID`
- `APPWRITE_API_KEY`
- `APPWRITE_DATABASE_ID`
- `APPWRITE_COLLECTION_MAP` (опційно): `lc:learning_centers,user_staff:staff`
- `APPWRITE_STORAGE_BUCKET_ID` (для file upload)
- `APPWRITE_MAX_UPLOAD_BYTES` (опційно, default 5MB)

## Що вже покращено
- Валідація полів для `filters` та `sort` (allow-list з pydantic schema полів).
- Нормалізація Appwrite технічних полів (`$id`, `$createdAt`, `$updatedAt`).
- Приховування `user_pass` з відповіді login.
- Константний порівнювач паролів (`hmac.compare_digest`).
- Реальний upload у Appwrite Storage + лінкування файлу в документ.

## Що ще варто зробити для production security
1. Перейти з plaintext-паролів на Argon2/Bcrypt hashes + optional pepper.
2. Замість `token = $id` впровадити JWT/Session токени з TTL, refresh та revoke.
3. Рознести Appwrite API keys за ролями (least privilege) і використовувати окремі ключі для read/write/admin.
4. Додати rate-limit + brute-force захист на `/api/login`.
5. Додати аудит-лог (хто/коли/що змінив), особливо для CRUD ендпоінтів.
6. Додати інтеграційні тести з тестовим Appwrite проектом (або мок-сервісом).
7. Додати централізований error mapping Appwrite -> HTTP коди (401/403/404/409).
8. Валідовувати mime-type/розширення файлів і антивірусний скан перед publish.
