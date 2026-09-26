import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceStatus
from app.schemas.common import StrippedStr


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
    correction_reason: Annotated[StrippedStr, Field(min_length=1, max_length=500)]


class AttendanceSummary(BaseModel):
    total_days: int
    present: int
    absent: int
    late: int
    half_day: int


class CalendarDay(BaseModel):
    date: date
    state: str
    is_weekend: bool
    before_joining: bool
    attendance_id: uuid.UUID | None = None
    check_in: datetime | None = None
    check_out: datetime | None = None
    worked_minutes: int | None = None
    overtime_minutes: int | None = None
    missing_punch: bool = False
    leave_name: str | None = None
    leave_status: str | None = None


class MonthCalendar(BaseModel):
    year: int
    month: int
    days: list[CalendarDay]