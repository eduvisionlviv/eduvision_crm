from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any

# --- Базова конфігурація ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Дозволяє створювати об'єкт як через name, так і через аліас (lc_name)
        from_attributes=True,   # Дозволяє читати дані з об'єктів ORM або класів
        extra='ignore'          # Ігнорує зайві поля з бази, яких немає в схемі (безпека)
    )

# --- 1. Схема для Навчальних Центрів (LC) ---
class LCSchema(BaseSchema):
    id: str
    name: str = Field(alias="lc_name")  # Мапінг: база lc_name -> API name
    address: Optional[str] = Field(default="", alias="lc_address")
    phone: Optional[str] = Field(default="", alias="lc_phone")
    # Якщо валюти немає в базі, ставимо UAH за замовчуванням
    currency: Optional[str] = Field(default="UAH") 
    
    # Поля для статистики (можна розширювати)
    staff_count: Optional[int] = Field(default=0)
    student_count: Optional[int] = Field(default=0)

# --- 2. Схема для Співробітників (User Staff) ---
class StaffSchema(BaseSchema):
    id: str
    name: str = Field(alias="user_name")
    email: str = Field(alias="user_mail")
    role: str = Field(alias="user_role")
    
    # Прив'язка до центру (важливо для фільтрації)
    # Якщо в базі поле називається інакше (напр. center_id), зміни alias тут
    center_id: Optional[str] = Field(default=None, alias="lc_id") 
    
    avatar: Optional[str] = Field(default="")
    created: Optional[str] = Field(default="")

# --- 3. Схема для Реєстрацій (Reg) ---
class RegSchema(BaseSchema):
    id: str
    admin_name: str
    email: str
    phone: str
    center_id: str
    status: str = Field(default="pending")
    created: Optional[str] = Field(default="")

# --- 4. Додаткові схеми (Заготовки на майбутнє) ---
# Можна додати схеми для Courses, Rooms, Students тут, коли створиш таблиці.

class CourseSchema(BaseSchema):
    id: str
    name: str
    description: Optional[str] = ""

class RoomSchema(BaseSchema):
    id: str
    name: str
    capacity: Optional[int] = 10
