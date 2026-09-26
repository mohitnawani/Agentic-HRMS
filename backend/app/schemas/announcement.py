# app/schemas/announcement.py
import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import StrippedStr


class AnnouncementCreate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=255)]
    body: Annotated[StrippedStr, Field(min_length=1, max_length=2000)]


class AnnouncementUpdate(BaseModel):
    title: Annotated[StrippedStr, Field(min_length=1, max_length=255)] | None = None
    body: Annotated[StrippedStr, Field(min_length=1, max_length=2000)] | None = None
    is_active: bool | None = None


class AnnouncementRead(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    created_by: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True
