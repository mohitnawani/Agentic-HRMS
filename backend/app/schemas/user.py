# app/schemas/user.py
import uuid

from pydantic import BaseModel, Field

from app.models.role import RoleEnum
from app.schemas.common import BlankableStr, EmailT, PasswordT


class UserCreate(BaseModel):
    email: EmailT
    password: PasswordT
    role: RoleEnum = RoleEnum.EMPLOYEE
    first_name: BlankableStr = Field(default=None, max_length=100)
    last_name: BlankableStr = Field(default=None, max_length=100)


class UserEmailUpdate(BaseModel):
    email: EmailT


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True
