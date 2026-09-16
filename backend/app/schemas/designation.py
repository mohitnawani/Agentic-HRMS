# app/schemas/designation.py
import uuid
from pydantic import BaseModel


class DesignationCreate(BaseModel):
    title: str


class DesignationUpdate(BaseModel):
    title: str | None = None


class DesignationRead(BaseModel):
    id: uuid.UUID
    title: str

    class Config:
        from_attributes = True