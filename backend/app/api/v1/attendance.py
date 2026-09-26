import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.attendance import AttendanceCorrection, AttendanceRead, AttendanceSummary, MonthCalendar
from app.services import attendance_service, employee_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _validate_range(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end date cannot be before start date",
        )
    if (start is not None and (start.year < 2000 or start.year > 2100)) or (
        end is not None and (end.year < 2000 or end.year > 2100)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dates must be between year 2000 and 2100",
        )


@router.post("/check-in", response_model=AttendanceRead, dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def check_in(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.check_in(db, employee.id)


@router.post("/check-out", response_model=AttendanceRead, dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def check_out(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.check_out(db, employee.id)


@router.get("/me", response_model=list[AttendanceRead], dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def my_history(
    start: date | None = Query(None), end: date | None = Query(None),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _validate_range(start, end)
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.get_history(db, employee.id, start, end)


@router.get("/me/summary", response_model=AttendanceSummary, dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def my_summary(
    year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.get_monthly_summary(db, employee.id, year, month)


@router.get("/me/calendar", response_model=MonthCalendar, dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def my_calendar(
    year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    days = await attendance_service.get_month_calendar(db, employee.id, employee.date_of_joining, year, month)
    return {"year": year, "month": month, "days": days}


@router.get("/{employee_id}", response_model=list[AttendanceRead], dependencies=[Depends(require_permission("attendance:read_all"))])
async def employee_history(
    employee_id: uuid.UUID, start: date | None = Query(None), end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    _validate_range(start, end)
    await employee_service.get_employee(db, employee_id)
    return await attendance_service.get_history(db, employee_id, start, end)


@router.get("/{employee_id}/calendar", response_model=MonthCalendar, dependencies=[Depends(require_permission("attendance:read_all"))])
async def employee_calendar(
    employee_id: uuid.UUID, year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee(db, employee_id)
    days = await attendance_service.get_month_calendar(db, employee.id, employee.date_of_joining, year, month)
    return {"year": year, "month": month, "days": days}


@router.patch("/{attendance_id}/correct", response_model=AttendanceRead, dependencies=[Depends(require_permission("attendance:correct"))])
async def correct(
    attendance_id: uuid.UUID, data: AttendanceCorrection,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await attendance_service.correct_attendance(db, attendance_id, current_user.id, data)