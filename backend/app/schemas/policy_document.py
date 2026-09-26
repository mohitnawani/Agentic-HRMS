import uuid
from datetime import datetime

from pydantic import BaseModel


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
