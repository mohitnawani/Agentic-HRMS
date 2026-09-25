"""Permission-enforced write tools used by the Action Agent."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.permissions import has_permission
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.department import DepartmentCreate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services import employee_service, leave_service


class WriteToolAccessDenied(PermissionError):
    """The authenticated actor is not permitted to perform an operation."""


class WriteToolConflict(ValueError):
    """The requested write conflicts with current database state."""


async def _actor_user(state: AgentState, db: AsyncSession) -> User:
    """Reload and verify the actor represented by trusted graph state."""
    try:
        user_id = uuid.UUID(str(state["user_id"]))
        state_role = RoleEnum(state["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WriteToolAccessDenied("Authenticated user context is missing.") from exc

    actor = await db.scalar(select(User).where(User.id == user_id))
    if actor is None or not actor.is_active or actor.role != state_role:
        raise WriteToolAccessDenied("Authenticated user context is invalid.")
    return actor


def _require(role: RoleEnum, permission: str) -> None:
    if not has_permission(role, permission):
        raise WriteToolAccessDenied(
            f"Your role does not have permission '{permission}'."
        )


def _translate_service_error(exc: HTTPException) -> WriteToolConflict:
    return WriteToolConflict(str(exc.detail))


async def create_employee(
    state: AgentState, db: AsyncSession, data: EmployeeCreate
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "employee:create")
    if data.role == RoleEnum.ADMIN and actor.role != RoleEnum.ADMIN:
        raise WriteToolAccessDenied("Only admins can create admin accounts.")
    try:
        employee = await employee_service.create_employee(db, data)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "employee_id": str(employee.id),
        "user_id": str(employee.user_id),
        "full_name": f"{employee.first_name} {employee.last_name}",
    }


async def update_employee(
    state: AgentState,
    db: AsyncSession,
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "employee:update")
    if not data.model_fields_set:
        raise WriteToolConflict("At least one employee field must be provided.")
    try:
        employee = await employee_service.update_employee(db, employee_id, data, actor)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "employee_id": str(employee.id),
        "full_name": f"{employee.first_name} {employee.last_name}",
        "updated_fields": sorted(data.model_fields_set),
    }


async def delete_employee(
    state: AgentState, db: AsyncSession, employee_id: uuid.UUID
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "employee:delete")
    target = await db.scalar(select(Employee).where(Employee.id == employee_id))
    if target is None:
        raise WriteToolConflict("Employee not found.")
    if target.user_id == actor.id:
        raise WriteToolAccessDenied("You cannot delete your own employee account.")
    try:
        await employee_service.delete_employee(db, employee_id, actor)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"employee_id": str(employee_id), "deleted": True}


async def approve_leave(
    state: AgentState, db: AsyncSession, request_id: uuid.UUID
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "leave:approve")
    try:
        request = await leave_service.approve_leave(db, request_id, actor.id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"request_id": str(request.id), "status": request.status.value}


async def reject_leave(
    state: AgentState, db: AsyncSession, request_id: uuid.UUID
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "leave:approve")
    try:
        request = await leave_service.reject_leave(db, request_id, actor.id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"request_id": str(request.id), "status": request.status.value}


async def create_department(
    state: AgentState, db: AsyncSession, data: DepartmentCreate
) -> dict[str, object]:
    actor = await _actor_user(state, db)
    _require(actor.role, "department:write")
    existing = await db.scalar(select(Department).where(Department.name == data.name))
    if existing is not None:
        raise WriteToolConflict("Department already exists.")
    department = Department(**data.model_dump())
    db.add(department)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise WriteToolConflict("Department already exists.") from exc
    await db.refresh(department)
    return {
        "department_id": str(department.id),
        "name": department.name,
        "description": department.description,
    }
