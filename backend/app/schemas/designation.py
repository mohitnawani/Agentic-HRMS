# app/schemas/designation.py
import uuid
from typing import Annotated
from pydantic import BaseModel, Field

from app.schemas.common import StrippedStr


class DesignationCreate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=100)]
    department_id: uuid.UUID


class DesignationUpdate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=100)] | None = None
    department_id: uuid.UUID | None = None


class DesignationRead(BaseModel):
    id: uuid.UUID
    title: str
    department_id: uuid.UUID
    department_name: str | None = None

    class Config:
        from_attributes = True