from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any

# --- Базова конфігурація ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Дозволяє створювати об'єкт як через name, так і через аліас
        from_attributes=True,   # Дозволяє читати дані з об'єктів PocketBase
        # ✅ ВИПРАВЛЕНО: 'forbid' змусить API видавати помилку, якщо в базі з'являться нові поля,
        # яких немає в схемі. Це захистить від "зникнення" даних.
        extra='forbid'          
    )

# --- 1. Схема для Навчальних Центрів (lc) ---
class LCSchema(BaseSchema):
    id: str
    name: str = Field(alias="lc_name")  # API: name <-> DB: lc_name
    address: Optional[str] = Field(default="", alias="lc_address")
    phone: Optional[str] = Field(default="", alias="lc_phone")
    currency: Optional[str] = Field(default="UAH") 
    
    # Поля для статистики
    staff_count: Optional[int] = Field(default=0)
    student_count: Optional[int] = Field(default=0)
    
    # Поля дати створення/оновлення, які завжди є в PocketBase
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 2. Схема для Співробітників (user_staff) ---
class StaffSchema(BaseSchema):
    id: str
    name: str = Field(alias="user_name")
    email: str = Field(alias="user_mail")
    role: str = Field(alias="user_access") 
    
    center_id: Optional[str] = Field(default=None, alias="lc_id") 
    
    avatar: Optional[str] = Field(default="")
    
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 3. Схема для Реєстрацій (reg) ---
class RegSchema(BaseSchema):
    id: str
    admin_name: str
    email: str
    phone: str
    center_id: str
    status: str = Field(default="pending")
    
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 4. Курси (courses) ---
class CourseSchema(BaseSchema):
    id: str
    name: str
    description: Optional[str] = ""
    center_id: Optional[str] = Field(default=None, alias="lc_id")
    
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 5. Кімнати/Аудиторії (rooms) ---
class RoomSchema(BaseSchema):
    id: str
    name: str
    capacity: Optional[int] = 10
    center_id: Optional[str] = Field(default=None, alias="lc_id")
    
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 6. Джерела лідів (sources) ---
class SourceSchema(BaseSchema):
    id: str
    n: str = Field(alias="name") 
    active: bool = True
    center_id: Optional[str] = Field(default=None, alias="lc_id") # Припускаю, що джерела теж прив'язані до LC
    
    created: Optional[str] = Field(default="")
    updated: Optional[str] = Field(default="")

# --- 7. НОВА ТАБЛИЦЯ (ШАБЛОН) ---
# 👇 ЗМІНИ ЦЕЙ КЛАС ПІД СВОЮ ТАБЛИЦЮ
class NewTableSchema(BaseSchema):
    id: str
    # Приклад полів (зміни на свої):
    name: str = Field(default="", alias="field_name_in_db") 
    status: Optional[str] = "active"
    description: Optional[str] = ""
    
    created: Optional[str] = ""
    updated: Optional[str] = ""
