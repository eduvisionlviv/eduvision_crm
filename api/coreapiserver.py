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
    for name in (primary, *fallbacks):
        val = os.getenv(name)
        if val: return val
    return default

# === МАПІНГ ТАБЛИЦЬ ===
TABLE_MAPPING = {
    "contacts": "contacts",
    "register": "register",
    "students": "crm_students",
    "parents": "crm_parents",
    "courses": "crm_courses",
    "enrollments": "crm_enrollments",
    "payments": "crm_payments",
    "bank_keys": "crm_bank_keys",
    "uni_base": "uni_base",
    "scheduled_tasks": "scheduled_tasks",
    "black_list": "black_list"
}

# === МАПІНГ ПОЛІВ ===
# Зліва: назва в коді Python -> Справа: Key (стовпець) в Appwrite (згідно ваших скріншотів)
FIELD_MAPPING = {
    # --- Загальні поля (contacts + register) ---
    "user_email": "user_email",
    "user_name":  "user_name",
    "pass_email": "pass_email",
    "user_phone": "user_phone",

    # --- Специфічні для contacts (image_09f603.png) ---
    "user_access":    "role",          # Код user_access -> База role
    "user_id":        "userId",        # Код user_id -> База userId
    "is_active":      "isActive",      # Код is_active -> База isActive
    "last_login":     "lastLogin",     # Код last_login -> База lastLogin
    "recovery_tg_id": "user_tg_id",    # Код recovery_tg_id -> База user_tg_id
    "auth_tokens":    "auth_tokens",
    "expires_at":     "expires_at",

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
    if not data: return data
    return {FIELD_MAPPING.get(k, k): v for k, v in data.items()}

def _map_output(doc):
    if not doc: return None
    new_doc = doc.copy()
    for db_k, v in doc.items():
        if db_k in REVERSE_FIELD_MAPPING:
            new_doc[REVERSE_FIELD_MAPPING[db_k]] = v
    return new_doc

class AppwriteAdapter:
    def __init__(self, table_name=None):
        self.db = _get_services()
        self.db_id = _get_env_value(ENV_DB_ID, *ALT_DB_IDS)
        self.table_name = TABLE_MAPPING.get(table_name, table_name)
        self.queries = []
        self.payload = None
        self.op = None
        self.single_doc = False

    def table(self, name):
        self.table_name = TABLE_MAPPING.get(name, name)
        return self

    def select(self, cols="*"):
        self.op = 'select'
        return self

    def eq(self, col, val):
        self.queries.append(Query.equal(FIELD_MAPPING.get(col, col), val))
        return self
    
    def gt(self, col, val):
        self.queries.append(Query.greater_than(FIELD_MAPPING.get(col, col), val))
        return self

    def lte(self, col, val):
        self.queries.append(Query.less_than_equal(FIELD_MAPPING.get(col, col), val))
        return self

    def single(self):
        self.single_doc = True
        return self

    def insert(self, data):
        self.op = 'insert'
        self.payload = _map_input(data)
        return self

    def update(self, data):
        self.op = 'update'
        self.payload = _map_input(data)
        return self
    
    def delete(self):
        self.op = 'delete'
        return self
    
    def in_(self, col, vals):
        self.queries.append(Query.contains(FIELD_MAPPING.get(col, col), vals))
        return self

    def execute(self):
        if not self.db_id or not self.db:
            log.error("❌ DB not configured")
            return type('R', (), {"data": None})

        try:
            if self.op == 'insert':
                res = self.db.create_document(self.db_id, self.table_name, ID.unique(), self.payload)
                return type('R', (), {"data": _map_output(res)})

            docs = self.db.list_documents(self.db_id, self.table_name, queries=self.queries)['documents']

            if self.op == 'update':
                updated = [self.db.update_document(self.db_id, self.table_name, d['$id'], self.payload) for d in docs]
                return type('R', (), {"data": [_map_output(d) for d in updated]})

            if self.op == 'delete':
                for d in docs:
                    self.db.delete_document(self.db_id, self.table_name, d['$id'])
                return type('R', (), {"data": True})

            data = [_map_output(d) for d in docs]
            final = data[0] if (self.single_doc and data) else data
            return type('R', (), {"data": final})

        except Exception as e:
            log.error(f"⚠️ Appwrite [{self.table_name}]: {e}")
            return type('R', (), {"data": None})

def get_client_for_table(name=None):
    return AppwriteAdapter(name)

def clear_cache(name):
    pass
