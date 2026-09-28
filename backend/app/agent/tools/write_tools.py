"""Permission-enforced write tools used by the Action Agent."""

import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.permissions import PERMISSIONS, has_permission
from app.models.announcement import Announcement
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.models.policy_document import PolicyDocument
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.schemas.attendance import AttendanceDateCorrection
from app.schemas.department import DepartmentCreate
from app.schemas.designation import DesignationCreate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.schemas.holiday import HolidayCreate
from app.schemas.leave import LeaveRequestCreate, LeaveTypeCreate
from app.services import (
    attendance_service,
    employee_service,
    leave_service,
    policy_service,
)


class WriteToolAccessDenied(PermissionError):
    """The authenticated actor is not permitted to perform an operation."""


class WriteToolConflict(ValueError):
    """The requested write conflicts with current database state."""


ACTION_PERMISSIONS = {
    "create_employee": "employee:create",
    "update_employee": "employee:update",
    "delete_employee": "employee:delete",
    "approve_leave": "leave:approve",
    "reject_leave": "leave:approve",
    "create_leave_type": "leave:type_write",
    "create_department": "department:write",
    "delete_department": "department:write",
    "create_designation": "designation:write",
    "delete_designation": "designation:write",
    "create_announcement": "announcement:write",
    "update_announcement": "announcement:write",
    "delete_announcement": "announcement:write",
    "create_holiday": "holiday:write",
    "delete_holiday": "holiday:write",
    "upload_policy": "policy:write",
    "delete_policy": "policy:write",
    "apply_leave": "leave:apply",
    "cancel_leave": "leave:apply",
    "check_in": "attendance:check_in_out",
    "check_out": "attendance:check_in_out",
    "correct_attendance": "attendance:correct",
}


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
        allowed = PERMISSIONS.get(permission, set())
        role_names = ", ".join(sorted(item.value.title() for item in allowed))
        suffix = f" Only {role_names} can do this." if role_names else ""
        raise WriteToolAccessDenied(
            f"Your role does not have permission to perform this action.{suffix}"
        )


async def authorize_write_tool(state: AgentState, db: AsyncSession, tool: str) -> User:
    """Apply the shared permission policy before collecting or executing an action."""
    permission = ACTION_PERMISSIONS.get(tool)
    if permission is None:
        raise WriteToolAccessDenied("This action is not permitted.")
    actor = await _actor_user(state, db)
    _require(actor.role, permission)
    return actor


def _translate_service_error(exc: HTTPException) -> WriteToolConflict:
    return WriteToolConflict(str(exc.detail))


async def create_employee(
    state: AgentState, db: AsyncSession, data: EmployeeCreate
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "create_employee")
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
    actor = await authorize_write_tool(state, db, "update_employee")
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
    actor = await authorize_write_tool(state, db, "delete_employee")
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
    actor = await authorize_write_tool(state, db, "approve_leave")
    try:
        request = await leave_service.approve_leave(db, request_id, actor.id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"request_id": str(request.id), "status": request.status.value}


async def reject_leave(
    state: AgentState, db: AsyncSession, request_id: uuid.UUID
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "reject_leave")
    try:
        request = await leave_service.reject_leave(db, request_id, actor.id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"request_id": str(request.id), "status": request.status.value}


async def create_leave_type(
    state: AgentState, db: AsyncSession, data: LeaveTypeCreate
) -> dict[str, object]:
    await authorize_write_tool(state, db, "create_leave_type")
    try:
        leave_type = await leave_service.create_leave_type(db, data)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "leave_type_id": str(leave_type.id),
        "name": leave_type.name,
        "default_annual_days": leave_type.default_annual_days,
    }


async def apply_leave(
    state: AgentState, db: AsyncSession, data: LeaveRequestCreate
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "apply_leave")
    employee = await db.scalar(select(Employee).where(Employee.user_id == actor.id))
    if employee is None:
        raise WriteToolConflict("No employee profile is linked to your account.")
    try:
        request = await leave_service.apply_leave(db, employee.id, data)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "request_id": str(request.id),
        "status": request.status.value,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
    }


async def preview_leave_application(
    state: AgentState, db: AsyncSession, data: LeaveRequestCreate
) -> dict[str, object]:
    """Run the same leave validation before asking the user to confirm."""
    actor = await authorize_write_tool(state, db, "apply_leave")
    employee = await db.scalar(select(Employee).where(Employee.user_id == actor.id))
    if employee is None:
        raise WriteToolConflict("No employee profile is linked to your account.")
    try:
        return await leave_service.validate_leave_request(db, employee.id, data)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc


async def cancel_leave(
    state: AgentState, db: AsyncSession, request_id: uuid.UUID
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "cancel_leave")
    employee = await db.scalar(select(Employee).where(Employee.user_id == actor.id))
    if employee is None:
        raise WriteToolConflict("No employee profile is linked to your account.")
    try:
        request = await leave_service.cancel_leave(db, request_id, employee.id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {"request_id": str(request.id), "status": request.status.value}


async def record_attendance_action(
    state: AgentState, db: AsyncSession, tool: str
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, tool)
    employee = await db.scalar(select(Employee).where(Employee.user_id == actor.id))
    if employee is None:
        raise WriteToolConflict("No employee profile is linked to your account.")
    try:
        record = (
            await attendance_service.check_in(db, employee.id)
            if tool == "check_in"
            else await attendance_service.check_out(db, employee.id)
        )
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "attendance_id": str(record.id),
        "date": record.date.isoformat(),
        "status": record.status.value,
        "check_in": record.check_in.isoformat() if record.check_in else None,
        "check_out": record.check_out.isoformat() if record.check_out else None,
    }


async def correct_employee_attendance(
    state: AgentState,
    db: AsyncSession,
    employee_id: uuid.UUID,
    attendance_date: date,
    data: AttendanceDateCorrection,
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "correct_attendance")
    employee = await db.scalar(select(Employee).where(Employee.id == employee_id))
    if employee is None:
        raise WriteToolConflict("Employee not found.")
    if attendance_date < employee.date_of_joining:
        raise WriteToolConflict(
            "Attendance date cannot be before the employee's joining date."
        )
    if attendance_date > datetime.now(UTC).date():
        raise WriteToolConflict("Future attendance cannot be corrected.")
    try:
        record = await attendance_service.correct_attendance_for_date(
            db, employee.id, attendance_date, actor.id, data
        )
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "attendance_id": str(record.id),
        "employee_id": str(employee.id),
        "employee": f"{employee.first_name} {employee.last_name}",
        "date": record.date.isoformat(),
        "status": record.status.value,
    }


async def create_department(
    state: AgentState, db: AsyncSession, data: DepartmentCreate
) -> dict[str, object]:
    await authorize_write_tool(state, db, "create_department")
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


async def delete_department(
    state: AgentState, db: AsyncSession, department_id: uuid.UUID
) -> dict[str, object]:
    await authorize_write_tool(state, db, "delete_department")
    department = await db.get(Department, department_id)
    if department is None:
        raise WriteToolConflict("Department not found.")
    name = department.name
    await db.delete(department)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise WriteToolConflict(
            "This department is still used by employees or designations and cannot be deleted."
        ) from exc
    return {"department_id": str(department_id), "name": name, "deleted": True}


async def create_designation(
    state: AgentState, db: AsyncSession, data: DesignationCreate
) -> dict[str, object]:
    await authorize_write_tool(state, db, "create_designation")
    department = await db.get(Department, data.department_id)
    if department is None:
        raise WriteToolConflict("Department not found.")
    existing = await db.scalar(
        select(Designation).where(func.lower(Designation.title) == data.title.lower())
    )
    if existing is not None:
        raise WriteToolConflict("Designation already exists.")
    designation = Designation(**data.model_dump())
    db.add(designation)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise WriteToolConflict("Designation already exists.") from exc
    await db.refresh(designation)
    return {
        "designation_id": str(designation.id),
        "title": designation.title,
        "department": department.name,
    }


async def delete_designation(
    state: AgentState, db: AsyncSession, designation_id: uuid.UUID
) -> dict[str, object]:
    await authorize_write_tool(state, db, "delete_designation")
    designation = await db.get(Designation, designation_id)
    if designation is None:
        raise WriteToolConflict("Designation not found.")
    title = designation.title
    await db.delete(designation)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise WriteToolConflict(
            "This designation is still assigned to employees and cannot be deleted."
        ) from exc
    return {"designation_id": str(designation_id), "title": title, "deleted": True}


async def create_announcement(
    state: AgentState, db: AsyncSession, data: AnnouncementCreate
) -> dict[str, object]:
    actor = await authorize_write_tool(state, db, "create_announcement")
    announcement = Announcement(**data.model_dump(), created_by=actor.id)
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return {
        "announcement_id": str(announcement.id),
        "title": announcement.title,
        "is_active": announcement.is_active,
    }


async def update_announcement(
    state: AgentState,
    db: AsyncSession,
    announcement_id: uuid.UUID,
    data: AnnouncementUpdate,
) -> dict[str, object]:
    await authorize_write_tool(state, db, "update_announcement")
    if not data.model_fields_set:
        raise WriteToolConflict("At least one announcement field must be provided.")
    announcement = await db.get(Announcement, announcement_id)
    if announcement is None:
        raise WriteToolConflict("Announcement not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(announcement, field, value)
    await db.commit()
    await db.refresh(announcement)
    return {
        "announcement_id": str(announcement.id),
        "title": announcement.title,
        "updated_fields": sorted(data.model_fields_set),
    }


async def delete_announcement(
    state: AgentState, db: AsyncSession, announcement_id: uuid.UUID
) -> dict[str, object]:
    await authorize_write_tool(state, db, "delete_announcement")
    announcement = await db.get(Announcement, announcement_id)
    if announcement is None:
        raise WriteToolConflict("Announcement not found.")
    title = announcement.title
    await db.delete(announcement)
    await db.commit()
    return {"announcement_id": str(announcement_id), "title": title, "deleted": True}


async def create_holiday(
    state: AgentState, db: AsyncSession, data: HolidayCreate
) -> dict[str, object]:
    await authorize_write_tool(state, db, "create_holiday")
    existing = await db.scalar(
        select(Holiday).where(
            func.lower(Holiday.name) == data.name.lower(), Holiday.date == data.date
        )
    )
    if existing is not None:
        raise WriteToolConflict("Holiday already exists.")
    holiday = Holiday(**data.model_dump())
    db.add(holiday)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise WriteToolConflict("Holiday already exists.") from exc
    await db.refresh(holiday)
    return {
        "holiday_id": str(holiday.id),
        "name": holiday.name,
        "date": holiday.date.isoformat(),
    }


async def delete_holiday(
    state: AgentState, db: AsyncSession, holiday_id: uuid.UUID
) -> dict[str, object]:
    await authorize_write_tool(state, db, "delete_holiday")
    holiday = await db.get(Holiday, holiday_id)
    if holiday is None:
        raise WriteToolConflict("Holiday not found.")
    result = {"holiday_id": str(holiday.id), "name": holiday.name, "date": holiday.date.isoformat(), "deleted": True}
    await db.delete(holiday)
    await db.commit()
    return result


async def complete_policy_upload(
    state: AgentState, db: AsyncSession, document_id: uuid.UUID
) -> dict[str, object]:
    """Verify an upload performed by the policy API before completing the agent action."""
    actor = await authorize_write_tool(state, db, "upload_policy")
    document = await db.scalar(
        select(PolicyDocument).where(
            PolicyDocument.id == document_id,
            PolicyDocument.uploaded_by == actor.id,
        )
    )
    if document is None:
        raise WriteToolConflict("The uploaded policy document could not be verified.")
    return {
        "document_id": str(document.id),
        "title": document.title,
        "category": document.category,
    }


async def delete_policy(
    state: AgentState, db: AsyncSession, document_id: uuid.UUID
) -> dict[str, object]:
    await authorize_write_tool(state, db, "delete_policy")
    try:
        document = await policy_service.delete_policy(db, document_id)
    except HTTPException as exc:
        raise _translate_service_error(exc) from exc
    return {
        "document_id": str(document.id),
        "title": document.title,
        "deleted": True,
    }
