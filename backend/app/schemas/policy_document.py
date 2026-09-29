import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import StrippedStr


class PolicyDocumentUpdate(BaseModel):
    title: StrippedStr = Field(min_length=1, max_length=255)
    category: StrippedStr = Field(min_length=1, max_length=100)


class PolicyDocumentRead(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    summary: str | None
    file_path: str
    uploaded_by: uuid.UUID
    version: int
    created_at: datetime

    class Config:
        from_attributes = True
