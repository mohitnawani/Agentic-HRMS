# app/schemas/user.py
import uuid

from pydantic import BaseModel

from app.models.role import RoleEnum
from app.schemas.common import EmailT


class UserCreate(BaseModel):
    email: EmailT
    password: str
    role: RoleEnum = RoleEnum.EMPLOYEE
    first_name: str | None = None
    last_name: str | None = None


class UserEmailUpdate(BaseModel):
    email: EmailT


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True
