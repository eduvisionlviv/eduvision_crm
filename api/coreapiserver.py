# api/coreapiserver.py
import os
import logging
import threading
from flask import g
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("coreapiserver")

_client = None
_databases = None

# === ЗМІННІ СЕРЕДОВИЩА ===
ENV_PROJECT_ID = "appwriteprojectid"
ALT_PROJECT_IDS = ("APPWRITE_PROJECT_ID", "APPWRITE_PROJECTID", "APPWRITE_PROJECT")

ENV_API_KEY    = "appwritepadmin"
ALT_API_KEYS   = ("APPWRITE_API_KEY", "APPWRITE_APIKEY", "APPWRITE_SECRET", "APPWRITE_KEY")

ENV_DB_ID      = "appwritedatabaseid"
ALT_DB_IDS     = ("APPWRITE_DATABASE_ID", "APPWRITE_DATABASEID", "APPWRITE_DB_ID", "APPWRITE_DBID")

ENV_ENDPOINT   = "APPWRITE_ENDPOINT"
ALT_ENDPOINTS  = ("APPWRITE_API_ENDPOINT", "APPWRITE_HOST")

def _get_env_value(primary: str, *fallbacks: str, default: str = None) -> str:
    """Отримує значення першої знайденої змінної середовища."""
    for name in (primary, *fallbacks):
        val = os.getenv(name)
        if val: return val
    return default

# === МАПІНГ ТАБЛИЦЬ (Код -> Appwrite) ===
TABLE_MAPPING = {
    # Основні (з ваших скріншотів)
    "contacts": "contacts",       # ID таблиці: contacts
    "register": "register",       # ID таблиці: register
    
    # CRM (стандартні)
    "students": "crm_students",
    "parents": "crm_parents",
    "courses": "crm_courses",
    "enrollments": "crm_enrollments",
    "payments": "crm_payments",
    "bank_keys": "crm_bank_keys",
    
    # Системні
    "uni_base": "uni_base",
    "scheduled_tasks": "scheduled_tasks",
    "black_list": "black_list"
}

# === МАПІНГ ПОЛІВ (Код -> Appwrite Columns) ===
FIELD_MAPPING = {
    # --- Таблиця CONTACTS ---
    # Змінна в коді  ->  Ваша колонка в базі
    "user_name":      "username",
    "user_access":    "role",
    "user_id":        "userId",
    "recovery_tg_id": "user_tg_id",
    
    # Поля, назви яких збігаються (для надійності)
    "user_email":     "user_email",
    "pass_email":     "pass_email",
    "user_phone":     "user_phone",
    
    # Поля сесії (ОБОВ'ЯЗКОВО СТВОРИТИ В APPWRITE)
    "auth_tokens":    "auth_tokens",
    "expires_at":     "expires_at",

    # --- Таблиця REGISTER ---
    # (Тут назви збігаються, додатковий мапінг не потрібен, але хай буде)
    "username":       "user_name",
    "passwordHash":   "pass_email",
    
    # --- CRM ---
    "full_name": "fullName",
    "birth_date": "birthDate",
    "parent_id": "parentId",
    "notes": "notes",
    "student_id": "studentId",
    "course_id": "courseId",
    "start_date": "startDate",
    "payment_type": "paymentType",
}

REVERSE_FIELD_MAPPING = {v: k for k, v in FIELD_MAPPING.items()}

def with_global_lock(app):
    lock = threading.RLock()
    @app.before_request
    def _acquire():
        lock.acquire()
        g._lock = True
    @app.after_request
    def _release(resp):
        if getattr(g, "_lock", False):
            try: lock.release()
            except: pass
        return resp
    @app.teardown_request
    def _teardown(_):
        if getattr(g, "_lock", False):
            try: lock.release()
            except: pass
    return app

def _get_services():
    global _client, _databases
    if _databases: return _databases

    ep = _get_env_value(ENV_ENDPOINT, *ALT_ENDPOINTS, default="https://cloud.appwrite.io/v1")
    pid = _get_env_value(ENV_PROJECT_ID, *ALT_PROJECT_IDS)
    key = _get_env_value(ENV_API_KEY, *ALT_API_KEYS)

    if not (pid and key):
        log.error("❌ Appwrite credentials missing!")
        return None

    _client = Client()
    _client.set_endpoint(ep).set_project(pid).set_key(key)
    _databases = Databases(_client)
    return _databases

def _map_input(data):
    """Конвертує ключі: Python -> Appwrite"""
    if not data: return data
    return {FIELD_MAPPING.get(k, k): v for k, v in data.items()}

def _map_output(doc):
    """Конвертує ключі: Appwrite -> Python"""
    if not doc: return None
    new_doc = doc.copy()
    for db_k, v in doc.items():
        if db_k in REVERSE_FIELD_MAPPING:
            new_doc[REVERSE_FIELD_MAPPING[db_k]] = v
    return new_doc

class AppwriteAdapter:
    def __init__(self, table_name=None):
        self.db_service = _get_services()
        self.db_id = _get_env_value(ENV_DB_ID, *ALT_DB_IDS)
        self.table_name = TABLE_MAPPING.get(table_name, table_name)
        self.queries = []
        self.data_payload = None
        self.op_type = None
        self.is_single = False

    def table(self, name):
        self.table_name = TABLE_MAPPING.get(name, name)
        return self

    def select(self, columns="*"):
        self.op_type = 'select'
        return self

    def eq(self, column, value):
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.equal(real_col, value))
        return self
    
    def gt(self, column, value):
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.greater_than(real_col, value))
        return self

    # ✅ Додано для TaskScheduler
    def lte(self, column, value):
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.less_than_equal(real_col, value))
        return self

    def single(self):
        self.is_single = True
        return self

    def insert(self, data):
        self.op_type = 'insert'
        self.data_payload = _map_input(data)
        return self

    def update(self, data):
        self.op_type = 'update'
        self.data_payload = _map_input(data)
        return self
    
    def delete(self):
        self.op_type = 'delete'
        return self
    
    def in_(self, column, values):
        real_col = FIELD_MAPPING.get(column, column)
        self.queries.append(Query.contains(real_col, values))
        return self

    def execute(self):
        if not self.db_id or not self.db_service:
            log.error("❌ DB not configured")
            return type('R', (), {"data": None})

        try:
            if self.op_type == 'insert':
                res = self.db_service.create_document(
                    self.db_id, self.table_name, ID.unique(), self.data_payload
                )
                return type('R', (), {"data": _map_output(res)})

            # Select for Update/Delete/List
            docs = self.db_service.list_documents(
                self.db_id, self.table_name, queries=self.queries
            )['documents']

            if self.op_type == 'update':
                updated = []
                for d in docs:
                    upd = self.db_service.update_document(
                        self.db_id, self.table_name, d['$id'], self.data_payload
                    )
                    updated.append(_map_output(upd))
                return type('R', (), {"data": updated})

            if self.op_type == 'delete':
                for d in docs:
                    self.db_service.delete_document(self.db_id, self.table_name, d['$id'])
                return type('R', (), {"data": True})

            # Select Result
            data = [_map_output(d) for d in docs]
            final = data[0] if (self.is_single and data) else data
            return type('R', (), {"data": final})

        except Exception as e:
            log.error(f"⚠️ Appwrite [{self.table_name}]: {e}")
            return type('R', (), {"data": None})

def get_client_for_table(name=None):
    return AppwriteAdapter(name)

def clear_cache(name):
    pass
