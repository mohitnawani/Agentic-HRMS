# app/schemas/holiday.py
import datetime
import uuid

from pydantic import BaseModel


class HolidayCreate(BaseModel):
    name: str
    date: datetime.date


class HolidayUpdate(BaseModel):
    name: str | None = None
    date: datetime.date | None = None


class HolidayRead(BaseModel):
    id: uuid.UUID
    name: str
    date: datetime.date

    class Config:
        from_attributes = True
