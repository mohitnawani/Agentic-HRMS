# app/schemas/department.py
import uuid
from typing import Annotated
from pydantic import BaseModel, Field

from app.schemas.common import BlankableStr, StrippedStr


class DepartmentCreate(BaseModel):
    name: Annotated[StrippedStr, Field(min_length=1, max_length=100)]
    description: Annotated[BlankableStr, Field(max_length=500)] = None


class DepartmentUpdate(BaseModel):
    name: Annotated[StrippedStr, Field(min_length=1, max_length=100)] | None = None
    description: Annotated[BlankableStr, Field(max_length=500)] = None


class DepartmentRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True