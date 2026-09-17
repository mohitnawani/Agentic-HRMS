import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.attendance import AttendanceCorrection, AttendanceRead, AttendanceSummary
from app.services import attendance_service, employee_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


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
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.get_history(db, employee.id, start, end)


@router.get("/me/summary", response_model=AttendanceSummary, dependencies=[Depends(require_permission("attendance:check_in_out"))])
async def my_summary(
    year: int = Query(...), month: int = Query(...),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await attendance_service.get_monthly_summary(db, employee.id, year, month)


@router.get("/{employee_id}", response_model=list[AttendanceRead], dependencies=[Depends(require_permission("attendance:read_all"))])
async def employee_history(
    employee_id: uuid.UUID, start: date | None = Query(None), end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await attendance_service.get_history(db, employee_id, start, end)


@router.patch("/{attendance_id}/correct", response_model=AttendanceRead, dependencies=[Depends(require_permission("attendance:correct"))])
async def correct(
    attendance_id: uuid.UUID, data: AttendanceCorrection,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await attendance_service.correct_attendance(db, attendance_id, current_user.id, data)