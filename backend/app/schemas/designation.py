# app/schemas/designation.py
import uuid
from typing import Annotated
from pydantic import BaseModel, Field

from app.schemas.common import StrippedStr


class DesignationCreate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=100)]


class DesignationUpdate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=100)] | None = None


class DesignationRead(BaseModel):
    id: uuid.UUID
    title: str

    class Config:
        from_attributes = True