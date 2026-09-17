import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.attendance import AttendanceStatus


class AttendanceRead(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    check_in: datetime | None
    check_out: datetime | None
    status: AttendanceStatus

    class Config:
        from_attributes = True


class AttendanceCorrection(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: AttendanceStatus | None = None
    correction_reason: str


class AttendanceSummary(BaseModel):
    total_days: int
    present: int
    absent: int
    late: int
    half_day: int