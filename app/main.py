from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Dict, List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from .database import Base, engine, get_db
from .models import ApiKeySecret, Course, Enrollment, Parent, Payment, Student, User
from .schemas import (
    ApiKeyCreate,
    ApiKeyOut,
    CourseCreate,
    CourseOut,
    EnrollmentCreate,
    EnrollmentOut,
    LoginRequest,
    ParentCreate,
    ParentOut,
    PaymentCreate,
    PaymentOut,
    StudentCreate,
    StudentOut,
    TokenResponse,
    UserCreate,
    UserOut,
)

app = FastAPI(title="EduVision CRM", version="0.1.0")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
active_tokens: Dict[str, int] = {}

FERNET_SECRET = os.getenv("FERNET_SECRET")
if FERNET_SECRET:
    fernet = Fernet(FERNET_SECRET)
else:
    generated = Fernet.generate_key()
    fernet = Fernet(generated)


def create_db() -> None:
    Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event() -> None:
    create_db()
    with next(get_db()) as db:
        ensure_default_admin(db)


def ensure_default_admin(db: Session) -> None:
    email = "gammmerx@gmail.com"
    password = "апроль 123456."
    admin = db.query(User).filter(User.email == email).first()
    if not admin:
        admin = User(
            email=email, hashed_password=pwd_context.hash(password), is_admin=True
        )
        db.add(admin)
        db.commit()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний email або пароль",
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    user_id = active_tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен недійсний")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Користувача не знайдено")
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Лише для адміністратора")
    return current_user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user.id
    return TokenResponse(access_token=token)


@app.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> UserOut:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email вже існує")
    user = User(
        email=payload.email,
        hashed_password=pwd_context.hash(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/parents", response_model=ParentOut)
def create_parent(
    payload: ParentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ParentOut:
    parent = Parent(**payload.dict())
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return parent


@app.post("/students", response_model=StudentOut)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StudentOut:
    student = Student(**payload.dict())
    db.add(student)
    db.commit()
    db.refresh(student)
    return StudentOut(
        id=student.id,
        full_name=student.full_name,
        birth_date=student.birth_date,
        age_years=student.age_in_years(),
        parent_id=student.parent_id,
        created_at=student.created_at,
    )


@app.get("/students", response_model=List[StudentOut])
def list_students(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> List[StudentOut]:
    students = db.query(Student).all()
    result: List[StudentOut] = []
    for student in students:
        result.append(
            StudentOut(
                id=student.id,
                full_name=student.full_name,
                birth_date=student.birth_date,
                age_years=student.age_in_years(),
                parent_id=student.parent_id,
                created_at=student.created_at,
            )
        )
    return result


@app.post("/courses", response_model=CourseOut)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CourseOut:
    course = Course(**payload.dict())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.post("/enrollments", response_model=EnrollmentOut)
def create_enrollment(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EnrollmentOut:
    enrollment = Enrollment(**payload.dict())
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@app.post("/payments", response_model=PaymentOut)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaymentOut:
    payment = Payment(**payload.dict())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@app.post("/api-keys", response_model=ApiKeyOut)
def store_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> ApiKeyOut:
    encrypted_key = fernet.encrypt(payload.api_key.encode()).decode()
    record = ApiKeySecret(provider=payload.provider, encrypted_key=encrypted_key, description=payload.description)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api-keys", response_model=List[ApiKeyOut])
def list_api_keys(db: Session = Depends(get_db), _: User = Depends(get_admin_user)) -> List[ApiKeyOut]:
    return db.query(ApiKeySecret).all()


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
