# app/schemas/user.py
import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.role import RoleEnum

# Same lenient rule as employees: allow internal company domains.
EmailT = Annotated[str, Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class UserCreate(BaseModel):
    email: EmailT
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
