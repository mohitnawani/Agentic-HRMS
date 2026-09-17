import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.leave import (
    LeaveBalanceRead, LeaveRequestCreate, LeaveRequestRead, LeaveTypeCreate, LeaveTypeRead,
)
from app.services import employee_service, leave_service

router = APIRouter(prefix="/leave", tags=["leave"])


@router.post("/types", response_model=LeaveTypeRead, dependencies=[Depends(require_permission("leave:type_write"))])
async def create_leave_type(data: LeaveTypeCreate, db: AsyncSession = Depends(get_db)):
    return await leave_service.create_leave_type(db, data)


@router.get("/types", response_model=list[LeaveTypeRead], dependencies=[Depends(require_permission("leave:apply"))])
async def list_leave_types(db: AsyncSession = Depends(get_db)):
    return await leave_service.list_leave_types(db)


@router.get("/balance", response_model=list[LeaveBalanceRead], dependencies=[Depends(require_permission("leave:apply"))])
async def my_balance(
    year: int = Query(default_factory=lambda: date.today().year),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await leave_service.get_balances(db, employee.id, year)


@router.post("/requests", response_model=LeaveRequestRead, dependencies=[Depends(require_permission("leave:apply"))])
async def apply_leave(
    data: LeaveRequestCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await leave_service.apply_leave(db, employee.id, data)


@router.get("/requests/me", response_model=list[LeaveRequestRead], dependencies=[Depends(require_permission("leave:apply"))])
async def my_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await leave_service.get_my_requests(db, employee.id)


@router.get("/requests/pending", response_model=list[LeaveRequestRead], dependencies=[Depends(require_permission("leave:read_all"))])
async def pending_requests(db: AsyncSession = Depends(get_db)):
    return await leave_service.get_pending_requests(db)


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestRead, dependencies=[Depends(require_permission("leave:approve"))])
async def approve(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await leave_service.approve_leave(db, request_id, current_user.id)


@router.post("/requests/{request_id}/reject", response_model=LeaveRequestRead, dependencies=[Depends(require_permission("leave:approve"))])
async def reject(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await leave_service.reject_leave(db, request_id, current_user.id)


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestRead, dependencies=[Depends(require_permission("leave:apply"))])
async def cancel(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await leave_service.cancel_leave(db, request_id, employee.id)