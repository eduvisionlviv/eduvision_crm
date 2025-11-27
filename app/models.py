from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base, utcnow


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)


class Parent(Base, TimestampMixin):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    students = relationship("Student", back_populates="parent")


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)

    parent = relationship("Parent", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student")
    payments = relationship("Payment", back_populates="student")

    def age_in_years(self, reference_date: Optional[date] = None) -> int:
        today = reference_date or date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    monthly_fee = Column(Float, nullable=True)

    enrollments = relationship("Enrollment", back_populates="course")


class Enrollment(Base, TimestampMixin):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="UAH", nullable=False)
    period = Column(String, nullable=False)  # e.g., "2024-09", "2024", "2024-Q1"
    method = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    student = relationship("Student", back_populates="payments")


class ApiKeySecret(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    encrypted_key = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
