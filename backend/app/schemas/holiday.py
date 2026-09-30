# app/schemas/holiday.py
import datetime
import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import StrippedStr


class HolidayCreate(BaseModel):
    name: Annotated[StrippedStr, Field(min_length=1, max_length=200)]
    date: datetime.date


class HolidayUpdate(BaseModel):
    name: Annotated[StrippedStr, Field(min_length=1, max_length=200)] | None = None
    date: datetime.date | None = None


class HolidayRead(BaseModel):
    id: uuid.UUID
    name: str
    date: datetime.date

    class Config:
        from_attributes = True
