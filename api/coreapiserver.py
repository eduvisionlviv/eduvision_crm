# api/coreapiserver.py
import os
import logging
import threading
from typing import Optional
from flask import g
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("coreapiserver")

_client = None
_databases = None


class _Response:
    def __init__(self, data=None, error: Optional[str] = None):
        self.data = data
        self.error = error


def _make_response(data=None, error: Optional[str] = None):
    return _Response(data=data, error=error)


def _get_env_value(primary: str, *fallbacks: str, default: str = None) -> str:
    """Return the first non-empty env var among primary and fallbacks."""

    for name in (primary, *fallbacks):
        value = os.getenv(name)
        if value:
            return value
    return default

# === НАЛАШТУВАННЯ ЗМІННИХ ===
# Використовуємо ваші назви змінних з Railway + популярні альтернативи
ENV_PROJECT_ID = "appwriteprojectid"
ALT_PROJECT_IDS = (
    "APPWRITE_PROJECT_ID",
    "APPWRITE_PROJECTID",
    "APPWRITE_PROJECT",
)

ENV_API_KEY    = "appwritepadmin"
ALT_API_KEYS   = (
    "APPWRITE_API_KEY",
    "APPWRITE_APIKEY",
    "APPWRITE_SECRET",
    "APPWRITE_KEY",
)

ENV_DB_ID      = "appwritedatabaseid"
ALT_DB_IDS     = (
    "APPWRITE_DATABASE_ID",
    "APPWRITE_DATABASEID",
    "APPWRITE_DB_ID",
    "APPWRITE_DBID",
)

ENV_ENDPOINT   = "APPWRITE_ENDPOINT"
ALT_ENDPOINTS  = (
    "APPWRITE_API_ENDPOINT",
    "APPWRITE_HOST",
    "appwriteendpoint",
    "appwrite_endpoint",
    "appwrite_api_endpoint",
    "appwrite_host",
)

# === МАПІНГ ТАБЛИЦЬ (Код -> Appwrite) ===
TABLE_MAPPING = {
    "contacts": "user_admin",  # Код шукає 'contacts', а йдемо в 'user_admin'
    "register": "register",    # Для заявок (якщо немає, створіть або замініть на іншу)
    "uni_base": "uni_base",
    # CRM модулі
    "students": "crm_students",
    "parents": "crm_parents",
    "courses": "crm_courses",
    "enrollments": "crm_enrollments",
    "payments": "crm_payments",
    "bank_keys": "crm_bank_keys",
}

# === МАПІНГ ПОЛІВ (Код <-> Appwrite) ===
# Ліворуч: як називає код (join.py). Праворуч: як у вас в базі (user_admin)
FIELD_MAPPING = {
    # ── Логін / admin users (user_admin)
    "user_email":    "email",
    "pass_email":    "passwordHash",
    "user_name":     "username",
    "user_access":   "role",
    "user_id":       "useradminId",
    "user_phone":    "user_phone",
    "auth_tokens":   "auth_tokens",
    "expires_at":    "expires_at",
    "recovery_tg_id": "recovery_tg_id",
    "recovery_code":  "recovery_code",
    "password_resets_time": "password_resets_time",

    # ── CRM: учні
    "full_name":    "fullName",
    "birth_date":   "birthDate",
    "parent_id":    "parentId",
    "notes":        "notes",
    "grade_level":  "gradeLevel",
    "enrollment_date": "enrollmentDate",
    "student_status":   "studentStatus",

    # ── CRM: батьки
    "phone":        "phone",
    "email":        "email",
    "preferred_contact_time": "preferredContactTime",
    "number_of_children":    "numberOfChildren",

    # ── CRM: курси
    "age_from":     "ageFrom",
    "age_to":       "ageTo",
    "description":  "description",
    "start_time":   "startTime",
    "end_time":     "endTime",
    "max_participants": "maxParticipants",

    # ── CRM: записи на курс
    "student_id":   "studentId",
    "course_id":    "courseId",
    "start_date":   "startDate",
    "status":       "status",
    "completion_date": "completionDate",

    # ── CRM: оплати
    "payment_id":   "paymentId",
    "amount":       "amount",
    "currency":     "currency",
    "payment_type": "paymentType",
    "period":       "period",
    "comment":      "comment",
    "payment_status": "status",

    # ── CRM: банківські ключі
    "provider":       "provider",
    "api_key_id":     "apiKeyId",
    "api_secret":     "apiSecret",
    "webhook_secret": "webhookSecret",
    "created_by":     "createdBy",
    "creation_date":  "creationDate",
    "updated_at":     "updatedAt",
}

# Створюємо зворотний словник для перекладу відповіді від бази
REVERSE_FIELD_MAPPING = {v: k for k, v in FIELD_MAPPING.items()}


def with_global_lock(app):
    """
    Serializes request handling with a single process-wide lock.

    Some legacy modules are not thread-safe; this keeps behaviour consistent
    with the prior Supabase deployment where requests were effectively
    serialized. The lock is released in both normal and error flows.
    """

    lock = threading.RLock()

    @app.before_request
    def _acquire_lock():  # pragma: no cover - flask lifecycle hook
        lock.acquire()
        g._global_lock_acquired = True

    @app.after_request
    def _release_lock(response):  # pragma: no cover - flask lifecycle hook
        if getattr(g, "_global_lock_acquired", False):
            try:
                lock.release()
            except RuntimeError:
                pass
        return response

    @app.teardown_request
    def _teardown_release(_):  # pragma: no cover - flask lifecycle hook
        if getattr(g, "_global_lock_acquired", False):
            try:
                lock.release()
            except RuntimeError:
                pass

    return app


def _mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def describe_appwrite_config():
    """Return a masked snapshot of Appwrite config to simplify debugging."""

    endpoint = _get_env_value(ENV_ENDPOINT, *ALT_ENDPOINTS, default="https://cloud.appwrite.io/v1")
    project_id = _get_env_value(ENV_PROJECT_ID, *ALT_PROJECT_IDS)
    api_key = _get_env_value(ENV_API_KEY, *ALT_API_KEYS)
    db_id = _get_env_value(ENV_DB_ID, *ALT_DB_IDS)

    return {
        "endpoint": endpoint,
        "project_id": _mask(project_id),
        "api_key": _mask(api_key),
        "database_id": _mask(db_id),
        "tables": TABLE_MAPPING,
    }

def _get_services():
    global _client, _databases
    if _databases:
        return _databases

    endpoint = _get_env_value(ENV_ENDPOINT, *ALT_ENDPOINTS, default="https://cloud.appwrite.io/v1")
    project_id = _get_env_value(ENV_PROJECT_ID, *ALT_PROJECT_IDS)
    api_key = _get_env_value(ENV_API_KEY, *ALT_API_KEYS)

    missing = [name for name, val in (
        (ENV_PROJECT_ID, project_id),
        (ENV_API_KEY, api_key),
    ) if not val]

    if missing:
        log.error("❌ Не задані змінні: %s", ", ".join(missing))
        raise RuntimeError(f"Відсутні змінні середовища: {', '.join(missing)}")

    _client = Client()
    _client.set_endpoint(endpoint)
    _client.set_project(project_id)
    _client.set_key(api_key)

    _databases = Databases(_client)
    cfg = describe_appwrite_config()
    log.info(
        "✅ Appwrite client initialized (endpoint=%s project=%s db=%s)",
        cfg.get("endpoint"),
        cfg.get("project_id"),
        cfg.get("database_id"),
    )
    if endpoint == "https://cloud.appwrite.io/v1" and not os.getenv(ENV_ENDPOINT):
        log.info("ℹ️ Використовується дефолтний Appwrite endpoint. Додайте %s якщо ваш інший.", ENV_ENDPOINT)
    return _databases

def _translate_input_data(data):
    """Перекладає словник даних з мови коду на мову бази"""
    if not data: return data
    new_data = {}
    for key, value in data.items():
        # Якщо є переклад — використовуємо його, інакше залишаємо як є
        new_key = FIELD_MAPPING.get(key, key)
        new_data[new_key] = value
    return new_data

def _translate_output_doc(doc):
    """Перекладає документ з мови бази на мову коду"""
    if not doc: return None
    # Appwrite повертає системні поля ($id), їх залишаємо
    new_doc = doc.copy()
    for db_key, val in doc.items():
        # Якщо це поле з нашого мапінгу — додаємо "псевдонім", який чекає код
        if db_key in REVERSE_FIELD_MAPPING:
            code_key = REVERSE_FIELD_MAPPING[db_key]
            new_doc[code_key] = val
            
    # Хак для user_id: код іноді хоче int, але Appwrite ID це string.
    # Якщо useradminId це число у вигляді рядка, код може впасти, якщо не перетворити.
    # Але join.py переважно працює з ним як з ID. Залишимо як є.
    return new_doc

class AppwriteAdapter:
    def __init__(self, table_name=None):
        self.db_service = _get_services()
        self.db_id = _get_env_value(ENV_DB_ID, *ALT_DB_IDS)
        self.raw_table_name = table_name
        self.table_name = TABLE_MAPPING.get(table_name, table_name)
        self.queries = []
        self.data_payload = None
        self.op_type = None
        self.is_single = False

    def table(self, name):
        self.raw_table_name = name
        self.table_name = TABLE_MAPPING.get(name, name)
        return self

    def select(self, columns="*"):
        self.op_type = 'select'
        return self

    def eq(self, column, value):
        # Перекладаємо назву колонки для пошуку
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.equal(real_col, value))
        return self
    
    def gt(self, column, value):
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.greater_than(real_col, value))
        return self

    def single(self):
        self.is_single = True
        return self

    def insert(self, data):
        self.op_type = 'insert'
        self.data_payload = _translate_input_data(data)
        return self

    def update(self, data):
        self.op_type = 'update'
        self.data_payload = _translate_input_data(data)
        return self

    def execute(self):
        if not self.db_id:
            log.error(
                "❌ Не задано %s (спробуйте також %s)",
                ENV_DB_ID,
                ", ".join(ALT_DB_IDS),
            )
            return _make_response(data=None, error="missing_database_id")

        try:
            # --- INSERT ---
            if self.op_type == 'insert':
                res = self.db_service.create_document(
                    self.db_id, self.table_name, ID.unique(), self.data_payload
                )
                return _make_response(data=_translate_output_doc(res))

            # --- SELECT / UPDATE SEARCH ---
            result = self.db_service.list_documents(
                self.db_id, self.table_name, queries=self.queries
            )
            documents = result['documents']

            # --- UPDATE ---
            if self.op_type == 'update':
                updated_list = []
                for doc in documents:
                    upd = self.db_service.update_document(
                        self.db_id, self.table_name, doc['$id'], self.data_payload
                    )
                    updated_list.append(_translate_output_doc(upd))
                return _make_response(data=updated_list)

            # --- SELECT RESULT ---
            if self.is_single:
                final_data = _translate_output_doc(documents[0]) if documents else None
            else:
                final_data = [_translate_output_doc(d) for d in documents]

            return _make_response(data=final_data)

        except Exception as e:
            log.error(f"⚠️ Appwrite Error in {self.table_name} ({self.op_type}): {e}")
            return _make_response(data=None, error=str(e))

def get_client_for_table(table_name: str = None):
    return AppwriteAdapter(table_name)

def clear_cache(name):
    pass
