import uuid

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.leave import LeaveRequestStatus
from app.schemas.common import StrippedStr


class LeaveTypeCreate(BaseModel):
    name: Annotated[StrippedStr, Field(min_length=1, max_length=100)]
    default_annual_days: int = Field(default=12, ge=0, le=60)


class LeaveTypeRead(BaseModel):
    id: uuid.UUID
    name: str
    default_annual_days: int

    class Config:
        from_attributes = True


class LeaveBalanceRead(BaseModel):
    leave_type_id: uuid.UUID
    leave_type_name: str
    year: int
    total_days: int
    used_days: int
    remaining_days: int

    class Config:
        from_attributes = True


class LeaveRequestCreate(BaseModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: Annotated[StrippedStr, Field(min_length=1, max_length=500)]


class LeaveRequestRead(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str
    status: LeaveRequestStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None

    class Config:
        from_attributes = True
