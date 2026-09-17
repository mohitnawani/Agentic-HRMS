# app/schemas/announcement.py
import uuid

from pydantic import BaseModel


class AnnouncementCreate(BaseModel):
    title: str
    body: str


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    is_active: bool | None = None


class AnnouncementRead(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    created_by: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True
