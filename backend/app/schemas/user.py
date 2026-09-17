# app/schemas/user.py
import uuid
from datetime import date

from pydantic import BaseModel, EmailStr

from app.models.role import RoleEnum


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.EMPLOYEE
    first_name: str | None = None
    last_name: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True
