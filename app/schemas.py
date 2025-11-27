from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ParentCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None


class ParentOut(ParentCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class StudentCreate(BaseModel):
    full_name: str
    birth_date: date
    parent_id: Optional[int] = None


class StudentOut(BaseModel):
    id: int
    full_name: str
    birth_date: date
    age_years: int
    parent_id: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    monthly_fee: Optional[float] = None


class CourseOut(CourseCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int
    start_date: date
    end_date: Optional[date] = None


class EnrollmentOut(EnrollmentCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class PaymentCreate(BaseModel):
    student_id: int
    amount: float
    currency: str = "UAH"
    period: str
    method: Optional[str] = None
    note: Optional[str] = None


class PaymentOut(PaymentCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ApiKeyCreate(BaseModel):
    provider: str
    api_key: str
    description: Optional[str] = None


class ApiKeyOut(BaseModel):
    id: int
    provider: str
    description: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
