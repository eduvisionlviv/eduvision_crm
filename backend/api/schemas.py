from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any

# --- Базова конфігурація ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Дозволяє створювати об'єкт як через name, так і через аліас
        from_attributes=True,   # Дозволяє читати дані з об'єктів PocketBase
        extra='ignore'          # Ігнорує зайві поля з бази, яких немає в схемі
    )

# --- 1. Схема для Навчальних Центрів (lc) ---
class LCSchema(BaseSchema):
    id: str
    name: str = Field(alias="lc_name")  # API: name <-> DB: lc_name
    address: Optional[str] = Field(default="", alias="lc_address")
    phone: Optional[str] = Field(default="", alias="lc_phone")
    currency: Optional[str] = Field(default="UAH") 
    
    # Поля для статистики (їх можна буде заповнювати окремо або через хуки)
    staff_count: Optional[int] = Field(default=0)
    student_count: Optional[int] = Field(default=0)

# --- 2. Схема для Співробітників (user_staff) ---
class StaffSchema(BaseSchema):
    id: str
    name: str = Field(alias="user_name")
    email: str = Field(alias="user_mail")
    # Важливо: мапінг прав доступу на роль
    role: str = Field(alias="user_access") 
    
    # Прив'язка до центру
    center_id: Optional[str] = Field(default=None, alias="lc_id") 
    
    avatar: Optional[str] = Field(default="")
    created: Optional[str] = Field(default="")

# --- 3. Схема для Реєстрацій (reg) ---
class RegSchema(BaseSchema):
    id: str
    admin_name: str
    email: str
    phone: str
    center_id: str
    status: str = Field(default="pending")
    created: Optional[str] = Field(default="")

# --- 4. Курси (courses) ---
class CourseSchema(BaseSchema):
    id: str
    name: str
    description: Optional[str] = ""
    # Якщо курси прив'язані до конкретного центру
    center_id: Optional[str] = Field(default=None, alias="lc_id")

# --- 5. Кімнати/Аудиторії (rooms) ---
class RoomSchema(BaseSchema):
    id: str
    name: str
    capacity: Optional[int] = 10
    center_id: Optional[str] = Field(default=None, alias="lc_id")

# --- 6. Джерела лідів (sources) ---
class SourceSchema(BaseSchema):
    id: str
    # Фронтенд використовує s.n, тому мапимо 'name' з бази в 'n'
    n: str = Field(alias="name") 
    active: bool = True
