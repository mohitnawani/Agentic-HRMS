import uuid

from datetime import date, datetime

from pydantic import BaseModel

from app.models.leave import LeaveRequestStatus


class LeaveTypeCreate(BaseModel):
    name: str
    default_annual_days: int = 12


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
    reason: str


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
