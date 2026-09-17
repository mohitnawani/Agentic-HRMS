import uuid

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.models.department import Department
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveRequestStatus
from app.models.user import User
from app.services import attendance_service, leave_service


async def employee_dashboard(db: AsyncSession, employee_id: uuid.UUID) -> dict:
    today = date.today()
    attendance_summary = await attendance_service.get_monthly_summary(db, employee_id, today.year, today.month)
    balances = await leave_service.get_balances(db, employee_id, today.year)

    pending_result = await db.execute(
        select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id, LeaveRequest.status == LeaveRequestStatus.PENDING
        )
    )
    return {
        "attendance_this_month": attendance_summary,
        "leave_balances": balances,
        "pending_leave_requests": pending_result.scalar_one(),
    }


async def _department_breakdown(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Department.name, func.count(Employee.id))
        .outerjoin(Employee, Employee.department_id == Department.id)
        .group_by(Department.name)
    )
    return {name: count for name, count in result.all()}


async def hr_dashboard(db: AsyncSession) -> dict:
    total_result = await db.execute(select(func.count()).select_from(Employee))
    total_employees = total_result.scalar_one()

    today = date.today()
    on_leave_result = await db.execute(
        select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
    )
    pending_result = await db.execute(
        select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status == LeaveRequestStatus.PENDING)
    )
    return {
        "total_employees": total_employees,
        "on_leave_today": on_leave_result.scalar_one(),
        "pending_approvals": pending_result.scalar_one(),
        "department_breakdown": await _department_breakdown(db),
    }


async def admin_dashboard(db: AsyncSession) -> dict:
    total_employees_result = await db.execute(select(func.count()).select_from(Employee))
    total_departments_result = await db.execute(select(func.count()).select_from(Department))
    active_users_result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
    )
    return {
        "total_employees": total_employees_result.scalar_one(),
        "total_departments": total_departments_result.scalar_one(),
        "active_users": active_users_result.scalar_one(),
        "department_breakdown": await _department_breakdown(db),
    }