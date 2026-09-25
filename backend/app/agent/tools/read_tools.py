"""Permission-aware, read-only HRMS tools used by the Database Agent."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.permissions import has_permission
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User
from app.services import attendance_service, leave_service


class ReadToolAccessDenied(PermissionError):
    """The authenticated graph actor is not allowed to read the resource."""


class ReadToolNotFound(LookupError):
    """The requested employee resource does not exist."""


def _actor(state: AgentState) -> tuple[uuid.UUID, RoleEnum]:
    """Read trusted identity only from graph state, never tool arguments."""
    try:
        return uuid.UUID(str(state["user_id"])), RoleEnum(state["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ReadToolAccessDenied("Authenticated user context is missing.") from exc


def _require(role: RoleEnum, permission: str) -> None:
    if not has_permission(role, permission):
        raise ReadToolAccessDenied(
            "Your role does not have permission to access this information."
        )


async def _employee_for_user(db: AsyncSession, user_id: uuid.UUID) -> Employee:
    employee = await db.scalar(select(Employee).where(Employee.user_id == user_id))
    if employee is None:
        raise ReadToolNotFound("No employee profile is linked to your account.")
    return employee


async def get_leave_balance(
    state: AgentState, db: AsyncSession, *, year: int | None = None
) -> dict[str, object]:
    """Return only the authenticated user's leave balances."""
    user_id, role = _actor(state)
    _require(role, "employee:read_self")
    employee = await _employee_for_user(db, user_id)
    selected_year = year or datetime.now(UTC).year
    balances = await leave_service.get_balances(db, employee.id, selected_year)
    return {
        "employee_id": str(employee.id),
        "year": selected_year,
        "balances": [
            {
                **balance,
                "leave_type_id": str(balance["leave_type_id"]),
            }
            for balance in balances
        ],
    }


async def get_attendance_summary(
    state: AgentState,
    db: AsyncSession,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, object]:
    """Return the authenticated user's attendance summary for one month."""
    user_id, role = _actor(state)
    _require(role, "employee:read_self")
    employee = await _employee_for_user(db, user_id)
    today = datetime.now(UTC).date()
    selected_year = year or today.year
    selected_month = month or today.month
    if not 1 <= selected_month <= 12:
        raise ValueError("month must be between 1 and 12")
    summary = await attendance_service.get_monthly_summary(
        db, employee.id, selected_year, selected_month
    )
    return {
        "employee_id": str(employee.id),
        "year": selected_year,
        "month": selected_month,
        **summary,
    }


async def list_employees(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    """List safe employee fields for Admin/HR actors only."""
    _, role = _actor(state)
    _require(role, "employee:read_all")
    statement = (
        select(Employee, User.email, Department.name, Designation.title)
        .join(User, User.id == Employee.user_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .order_by(Employee.first_name, Employee.last_name, Employee.id)
    )
    rows = (await db.execute(statement)).all()
    return [
        {
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "full_name": f"{employee.first_name} {employee.last_name}",
            "email": email,
            "department": department,
            "designation": designation,
        }
        for employee, email, department, designation in rows
    ]


async def get_employee_details(
    state: AgentState,
    db: AsyncSession,
    *,
    employee_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Return safe details, restricting employees to their own profile."""
    user_id, role = _actor(state)
    if employee_id is None:
        actor_employee = await _employee_for_user(db, user_id)
        target_id = actor_employee.id
        _require(role, "employee:read_self")
    elif has_permission(role, "employee:read_all"):
        target_id = employee_id
    else:
        actor_employee = await _employee_for_user(db, user_id)
        if employee_id != actor_employee.id:
            raise ReadToolAccessDenied(
                "Your role does not have permission to access this information."
            )
        target_id = employee_id
        _require(role, "employee:read_self")

    statement = (
        select(Employee, User.email, Department.name, Designation.title)
        .join(User, User.id == Employee.user_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .where(Employee.id == target_id)
    )
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise ReadToolNotFound("Employee not found.")
    employee, email, department, designation = row
    return {
        "employee_id": str(employee.id),
        "employee_code": employee.employee_code,
        "full_name": f"{employee.first_name} {employee.last_name}",
        "email": email,
        "phone": employee.phone,
        "date_of_joining": employee.date_of_joining.isoformat(),
        "department": department,
        "designation": designation,
    }
