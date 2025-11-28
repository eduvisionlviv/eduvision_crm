# api/coreapiserver.py
import os
import logging
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("coreapiserver")

_client = None
_databases = None

# === НАЛАШТУВАННЯ ЗМІННИХ ===
# Використовуємо ваші назви змінних з Railway
ENV_PROJECT_ID = "appwriteprojectid"
ENV_API_KEY    = "appwritepadmin"
ENV_DB_ID      = "appwritedatabaseid"
ENV_ENDPOINT   = "APPWRITE_ENDPOINT"

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
    # Код            # Ваша база
    "user_email":    "email",
    "pass_email":    "passwordHash",
    "user_name":     "username",
    "user_access":   "role",
    "user_id":       "useradminId",
    # "user_phone":  "user_phone",   <-- Це поле треба додати в базу!
    # "auth_tokens": "auth_tokens",  <-- Це поле треба додати в базу!

    # CRM: учні
    "full_name": "fullName",
    "birth_date": "birthDate",
    "parent_id": "parentId",
    "notes": "notes",
    "enrollment_date": "enrollmentDate",
    "grade_level": "gradeLevel",
    "student_status": "studentStatus",

    # CRM: батьки
    "full_name": "fullName",
    "phone": "phone",
    "email": "email",
    "notes": "notes",
    "api_key_id": "apiKeyId",
    "api_secret": "apiSecret",
    "webhook_secret": "webhookSecret",
    "created_by": "createdBy",

    # CRM: курси
    "name": "name",
    "description": "description",
    "age_from": "ageFrom",
    "age_to": "ageTo",
    "start_time": "startTime",
    "end_time": "endTime",
    "max_participants": "maxParticipants",

    # CRM: запис на курс
    "status": "status",
    "student_id": "studentId",
    "course_id": "courseId",
    "start_date": "startDate",
    "completion_date": "completionDate",

    # CRM: оплати
    "student_id": "studentId",
    "amount": "amount",
    "currency": "currency",
    "period": "period",
    "comment": "comment",
    "payment_type": "paymentType",
    "payment_id": "paymentId",
    "payment_method": "paymentMethod",
    "payment_date": "paymentDate",
}

# Створюємо зворотний словник для перекладу відповіді від бази
REVERSE_FIELD_MAPPING = {v: k for k, v in FIELD_MAPPING.items()}

def _get_services():
    global _client, _databases
    if _databases:
        return _databases
    
    endpoint = os.getenv(ENV_ENDPOINT, "https://cloud.appwrite.io/v1")
    project_id = os.getenv(ENV_PROJECT_ID)
    api_key = os.getenv(ENV_API_KEY)

    if not project_id or not api_key:
        log.error(f"❌ Не задані змінні: {ENV_PROJECT_ID} або {ENV_API_KEY}")
    
    _client = Client()
    _client.set_endpoint(endpoint)
    _client.set_project(project_id)
    _client.set_key(api_key)
    
    _databases = Databases(_client)
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
        self.db_id = os.getenv(ENV_DB_ID)
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
            log.error(f"❌ Не задано {ENV_DB_ID}")
            return type('Response', (object,), {"data": None})

        try:
            # --- INSERT ---
            if self.op_type == 'insert':
                res = self.db_service.create_document(
                    self.db_id, self.table_name, ID.unique(), self.data_payload
                )
                return type('Response', (object,), {"data": _translate_output_doc(res)})

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
                return type('Response', (object,), {"data": updated_list})

            # --- SELECT RESULT ---
            if self.is_single:
                final_data = _translate_output_doc(documents[0]) if documents else None
            else:
                final_data = [_translate_output_doc(d) for d in documents]
            
            return type('Response', (object,), {"data": final_data})

        except Exception as e:
            log.error(f"⚠️ Appwrite Error in {self.table_name} ({self.op_type}): {e}")
            return type('Response', (object,), {"data": None})

def get_client_for_table(table_name: str = None):
    return AppwriteAdapter(table_name)

def clear_cache(name):
    pass
