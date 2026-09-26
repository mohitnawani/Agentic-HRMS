"""Idempotent production bootstrap for a newly migrated database."""

import asyncio
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import async_session
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.models.role import RoleEnum
from app.models.user import User


async def _get_or_create_department(session, name: str) -> Department:
    department = await session.scalar(select(Department).where(Department.name == name))
    if department is None:
        department = Department(name=name)
        session.add(department)
        await session.flush()
    return department


async def _get_or_create_designation(session, title: str) -> Designation:
    designation = await session.scalar(select(Designation).where(Designation.title == title))
    if designation is None:
        designation = Designation(title=title)
        session.add(designation)
        await session.flush()
    return designation


async def _get_or_create_leave_type(session, name: str, days: int) -> LeaveType:
    leave_type = await session.scalar(select(LeaveType).where(LeaveType.name == name))
    if leave_type is None:
        leave_type = LeaveType(name=name, default_annual_days=days)
        session.add(leave_type)
        await session.flush()
    return leave_type


def _admin_credentials() -> tuple[str, str] | None:
    if settings.bootstrap_admin_email is None and settings.bootstrap_admin_password is None:
        return None
    if settings.bootstrap_admin_email is None or settings.bootstrap_admin_password is None:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set together"
        )
    try:
        email = validate_email(
            settings.bootstrap_admin_email, check_deliverability=False
        ).normalized.lower()
    except EmailNotValidError as exc:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL is not a valid email address") from exc
    password = settings.bootstrap_admin_password.get_secret_value()
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")
    if len(password.encode("utf-8")) > 72:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD cannot exceed 72 bytes")
    return email, password


async def bootstrap() -> None:
    credentials = _admin_credentials()
    today = datetime.now(UTC).date()
    async with async_session() as session:
        hr_department = await _get_or_create_department(session, "Human Resources")
        await _get_or_create_department(session, "Engineering")
        manager = await _get_or_create_designation(session, "Manager")
        await _get_or_create_designation(session, "HR Executive")
        await _get_or_create_designation(session, "Software Engineer")
        leave_types = [
            await _get_or_create_leave_type(session, "Casual Leave", 12),
            await _get_or_create_leave_type(session, "Sick Leave", 6),
        ]

        if credentials is not None:
            email, password = credentials
            user = await session.scalar(
                select(User).where(func.lower(User.email) == email)
            )
            if user is not None and user.role != RoleEnum.ADMIN:
                raise RuntimeError(
                    "BOOTSTRAP_ADMIN_EMAIL already belongs to a non-admin user"
                )
            if user is None:
                user = User(
                    email=email,
                    hashed_password=hash_password(password),
                    role=RoleEnum.ADMIN,
                    is_active=True,
                )
                session.add(user)
                await session.flush()

            employee = await session.scalar(
                select(Employee).where(Employee.user_id == user.id)
            )
            if employee is None:
                employee = Employee(
                    user_id=user.id,
                    first_name="System",
                    last_name="Administrator",
                    date_of_joining=today,
                    department_id=hr_department.id,
                    designation_id=manager.id,
                )
                session.add(employee)
                await session.flush()
                for leave_type in leave_types:
                    session.add(
                        LeaveBalance(
                            employee_id=employee.id,
                            leave_type_id=leave_type.id,
                            year=today.year,
                            total_days=leave_type.default_annual_days,
                            used_days=0,
                        )
                    )

        await session.commit()
    print("Database bootstrap completed.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
