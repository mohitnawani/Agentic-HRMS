import uuid
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveRequest, LeaveRequestStatus, LeaveType
from app.schemas.leave import LeaveRequestCreate, LeaveTypeCreate

# A single request may not span more than this many days.
MAX_LEAVE_SPAN_DAYS = 30


async def _get_leave_type_or_404(db: AsyncSession, leave_type_id: uuid.UUID) -> LeaveType:
    leave_type = await db.scalar(select(LeaveType).where(LeaveType.id == leave_type_id))
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave type not found")
    return leave_type


async def _reject_overlapping_request(
    db: AsyncSession, employee_id: uuid.UUID, start: date, end: date
) -> None:
    clash = await db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_([LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    )
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An overlapping pending or approved leave request already exists",
        )


# --- Leave Types (Admin) ---

async def create_leave_type(db: AsyncSession, data: LeaveTypeCreate) -> LeaveType:
    existing = await db.execute(
        select(LeaveType).where(func.lower(LeaveType.name) == data.name.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave type already exists")
    leave_type = LeaveType(**data.model_dump())
    db.add(leave_type)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave type already exists")
    await db.refresh(leave_type)
    return leave_type


async def list_leave_types(db: AsyncSession) -> list[LeaveType]:
    result = await db.execute(select(LeaveType))
    return list(result.scalars().all())


# --- Balances ---

async def initialize_balances_for_employee(db: AsyncSession, employee_id: uuid.UUID) -> None:
    """Called when a new employee is created — gives them a balance row per existing leave type."""
    year = date.today().year
    result = await db.execute(select(LeaveType))
    leave_types = result.scalars().all()
    for lt in leave_types:
        db.add(LeaveBalance(
            employee_id=employee_id, leave_type_id=lt.id, year=year,
            total_days=lt.default_annual_days, used_days=0,
        ))
    await db.commit()


async def get_balances(db: AsyncSession, employee_id: uuid.UUID, year: int) -> list[dict]:
    result = await db.execute(
        select(LeaveBalance, LeaveType)
        .join(LeaveType, LeaveBalance.leave_type_id == LeaveType.id)
        .where(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year)
    )
    rows = result.all()
    return [
        {
            "leave_type_id": bal.leave_type_id,
            "leave_type_name": lt.name,
            "year": bal.year,
            "total_days": bal.total_days,
            "used_days": bal.used_days,
            "remaining_days": bal.total_days - bal.used_days,
        }
        for bal, lt in rows
    ]


def _leave_days(start: date, end: date) -> int:
    return (end - start).days + 1


# --- Requests ---

async def apply_leave(db: AsyncSession, employee_id: uuid.UUID, data: LeaveRequestCreate) -> LeaveRequest:
    if data.end_date < data.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date before start_date")

    days_requested = _leave_days(data.start_date, data.end_date)
    if days_requested > MAX_LEAVE_SPAN_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A single request cannot exceed {MAX_LEAVE_SPAN_DAYS} days",
        )
    if data.end_date.year != data.start_date.year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave requests cannot span calendar years",
        )

    await _get_leave_type_or_404(db, data.leave_type_id)
    await _reject_overlapping_request(db, employee_id, data.start_date, data.end_date)
    year = data.start_date.year

    balance_result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == data.leave_type_id,
            LeaveBalance.year == year,
        )
    )
    balance = balance_result.scalar_one_or_none()
    if balance is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No leave balance found for this type/year")
    if (balance.total_days - balance.used_days) < days_requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient leave balance")

    leave_request = LeaveRequest(employee_id=employee_id, **data.model_dump())
    db.add(leave_request)
    await db.commit()
    await db.refresh(leave_request)
    return leave_request


async def get_my_requests(db: AsyncSession, employee_id: uuid.UUID) -> list[LeaveRequest]:
    result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.employee_id == employee_id).order_by(LeaveRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def get_pending_requests(db: AsyncSession) -> list[LeaveRequest]:
    result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.status == LeaveRequestStatus.PENDING)
    )
    return list(result.scalars().all())


async def _get_request_or_404(db: AsyncSession, request_id: uuid.UUID) -> LeaveRequest:
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == request_id))
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return req


async def approve_leave(db: AsyncSession, request_id: uuid.UUID, reviewer_id: uuid.UUID) -> LeaveRequest:
    req = await _get_request_or_404(db, request_id)
    if req.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be approved")

    requester = await db.scalar(select(Employee.user_id).where(Employee.id == req.employee_id))
    if requester is not None and requester == reviewer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve your own leave request")

    days = _leave_days(req.start_date, req.end_date)
    balance_result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == req.employee_id,
            LeaveBalance.leave_type_id == req.leave_type_id,
            LeaveBalance.year == req.start_date.year,
        )
    )
    balance = balance_result.scalar_one_or_none()
    if balance is None or (balance.total_days - balance.used_days) < days:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance at approval time")

    balance.used_days += days
    req.status = LeaveRequestStatus.APPROVED
    req.reviewed_by = reviewer_id
    req.reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(req)
    return req


async def reject_leave(db: AsyncSession, request_id: uuid.UUID, reviewer_id: uuid.UUID) -> LeaveRequest:
    req = await _get_request_or_404(db, request_id)
    if req.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be rejected")

    requester = await db.scalar(select(Employee.user_id).where(Employee.id == req.employee_id))
    if requester is not None and requester == reviewer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot review your own leave request")
    req.status = LeaveRequestStatus.REJECTED
    req.reviewed_by = reviewer_id
    req.reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(req)
    return req


async def cancel_leave(db: AsyncSession, request_id: uuid.UUID, employee_id: uuid.UUID) -> LeaveRequest:
    req = await _get_request_or_404(db, request_id)
    if req.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your leave request")
    if req.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be cancelled")
    req.status = LeaveRequestStatus.CANCELLED
    await db.commit()
    await db.refresh(req)
    return req