"""Idempotent production bootstrap for a newly migrated database."""

import asyncio
from datetime import UTC, date, datetime, time, timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import async_session
from app.models.announcement import Announcement
from app.models.attendance import Attendance, AttendanceStatus
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.models.leave import (
    LeaveBalance,
    LeaveRequest,
    LeaveRequestStatus,
    LeaveType,
)
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


# ---------------------------------------------------------------------------
# Demo seed data (fresh deploys only; every insert is get-or-create).
# ---------------------------------------------------------------------------

DEMO_PASSWORD = "DemoPass123!"

# email, role, first name, last name, department key, designation key,
# employee code, date of joining.
DEMO_TEAM: tuple[tuple[str, RoleEnum, str, str, str, str, str, date], ...] = (
    ("admin.demo@company.com", RoleEnum.ADMIN, "Vikram", "Malhotra", "hr", "manager", "EMP-1001", date(2022, 4, 1)),
    ("hr.demo@company.com", RoleEnum.HR, "Priya", "Nair", "hr", "hr_exec", "EMP-1002", date(2023, 1, 15)),
    ("rahul.verma@company.com", RoleEnum.EMPLOYEE, "Rahul", "Verma", "eng", "swe", "EMP-1003", date(2023, 6, 1)),
    ("amit.patel@company.com", RoleEnum.EMPLOYEE, "Amit", "Patel", "eng", "swe", "EMP-1004", date(2023, 9, 12)),
    ("vaishali.gupta@company.com", RoleEnum.EMPLOYEE, "Vaishali", "Gupta", "eng", "swe", "EMP-1005", date(2024, 2, 5)),
    ("sneha.reddy@company.com", RoleEnum.EMPLOYEE, "Sneha", "Reddy", "hr", "hr_exec", "EMP-1006", date(2024, 5, 20)),
    ("arjun.mehta@company.com", RoleEnum.EMPLOYEE, "Arjun", "Mehta", "eng", "swe", "EMP-1007", date(2024, 8, 11)),
    ("kavya.iyer@company.com", RoleEnum.EMPLOYEE, "Kavya", "Iyer", "eng", "swe", "EMP-1008", date(2025, 3, 3)),
)

DEMO_HOLIDAYS: tuple[tuple[str, date], ...] = (
    ("Gandhi Jayanti", date(2026, 10, 2)),
    ("Christmas Day", date(2026, 12, 25)),
    ("New Year Day", date(2027, 1, 1)),
)

DEMO_ANNOUNCEMENTS: tuple[tuple[str, str], ...] = (
    (
        "Welcome to the new HRMS portal",
        "Attendance, leave requests, policies, and the HR assistant are now "
        "available in one place. Please complete your profile details this week.",
    ),
    (
        "Year-end leave reminders",
        "Casual leave balances reset in January. Apply for pending 2026 leaves "
        "before December 20 so approvals finish on time.",
    ),
)


async def _get_or_create_user(session, email: str, role: RoleEnum, password_hash: str) -> User:
    user = await session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(email=email, hashed_password=password_hash, role=role, is_active=True)
        session.add(user)
        await session.flush()
    return user


async def _ensure_employee(
    session,
    user: User,
    first_name: str,
    last_name: str,
    date_of_joining: date,
    department_id,
    designation_id,
    employee_code: str,
) -> Employee:
    employee = await session.scalar(select(Employee).where(Employee.user_id == user.id))
    if employee is None:
        code_taken = await session.scalar(
            select(Employee).where(Employee.employee_code == employee_code)
        )
        employee = Employee(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            date_of_joining=date_of_joining,
            department_id=department_id,
            designation_id=designation_id,
            employee_code=None if code_taken is not None else employee_code,
        )
        session.add(employee)
        await session.flush()
    return employee


async def _ensure_leave_balances(session, employee: Employee, leave_types, year: int) -> None:
    for leave_type in leave_types:
        existing = await session.scalar(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.year == year,
            )
        )
        if existing is None:
            session.add(
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=leave_type.id,
                    year=year,
                    total_days=leave_type.default_annual_days,
                    used_days=0,
                )
            )
    await session.flush()


async def _seed_demo_data(session, *, departments, designations, leave_types, today: date) -> None:
    """Seed a small demo team plus sample HR records. Safe to re-run."""
    demo_hash = hash_password(DEMO_PASSWORD)
    employees_by_email: dict[str, Employee] = {}

    for email, role, first, last, dept_key, desig_key, code, doj in DEMO_TEAM:
        user = await _get_or_create_user(session, email, role, demo_hash)
        employee = await _ensure_employee(
            session,
            user,
            first,
            last,
            doj,
            departments[dept_key].id,
            designations[desig_key].id,
            code,
        )
        await _ensure_leave_balances(session, employee, leave_types, today.year)
        employees_by_email[email] = employee

    casual = next(lt for lt in leave_types if lt.name == "Casual Leave")
    sick = next(lt for lt in leave_types if lt.name == "Sick Leave")
    admin_user = await session.scalar(
        select(User).where(func.lower(User.email) == "admin.demo@company.com")
    )

    # One pending + one approved leave request so both queues have content.
    rahul = employees_by_email["rahul.verma@company.com"]
    pending = await session.scalar(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == rahul.id,
            LeaveRequest.start_date == today + timedelta(days=5),
        )
    )
    if pending is None:
        session.add(
            LeaveRequest(
                employee_id=rahul.id,
                leave_type_id=casual.id,
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=6),
                reason="Family function in hometown",
                status=LeaveRequestStatus.PENDING,
            )
        )

    amit = employees_by_email["amit.patel@company.com"]
    approved = await session.scalar(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == amit.id,
            LeaveRequest.start_date == today - timedelta(days=10),
        )
    )
    if approved is None:
        session.add(
            LeaveRequest(
                employee_id=amit.id,
                leave_type_id=sick.id,
                start_date=today - timedelta(days=10),
                end_date=today - timedelta(days=9),
                reason="Down with fever",
                status=LeaveRequestStatus.APPROVED,
                reviewed_by=admin_user.id if admin_user else None,
                reviewed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        balance = await session.scalar(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == amit.id,
                LeaveBalance.leave_type_id == sick.id,
                LeaveBalance.year == today.year,
            )
        )
        if balance is not None:
            balance.used_days += 2
    await session.flush()

    # Attendance for the last 5 weekdays so dashboards/charts have content.
    seeded_days = 0
    lookback = 1
    while seeded_days < 5 and lookback <= 10:
        day = today - timedelta(days=lookback)
        lookback += 1
        if day.weekday() >= 5:  # skip weekends
            continue
        for employee in employees_by_email.values():
            exists = await session.scalar(
                select(Attendance).where(
                    Attendance.employee_id == employee.id, Attendance.date == day
                )
            )
            if exists is None:
                session.add(
                    Attendance(
                        employee_id=employee.id,
                        date=day,
                        check_in=datetime.combine(day, time(9, 30)),
                        check_out=datetime.combine(day, time(18, 30)),
                        status=AttendanceStatus.PRESENT,
                    )
                )
        seeded_days += 1
    await session.flush()

    for name, day in DEMO_HOLIDAYS:
        exists = await session.scalar(select(Holiday).where(Holiday.name == name))
        if exists is None:
            session.add(Holiday(name=name, date=day))
    await session.flush()

    if admin_user is not None:
        for title, body in DEMO_ANNOUNCEMENTS:
            exists = await session.scalar(
                select(Announcement).where(Announcement.title == title)
            )
            if exists is None:
                session.add(
                    Announcement(
                        title=title, body=body, created_by=admin_user.id, is_active=True
                    )
                )
    await session.flush()


async def bootstrap() -> None:
    credentials = _admin_credentials()
    today = datetime.now(UTC).date()
    async with async_session() as session:
        hr_department = await _get_or_create_department(session, "Human Resources")
        engineering = await _get_or_create_department(session, "Engineering")
        manager = await _get_or_create_designation(session, "Manager")
        hr_exec = await _get_or_create_designation(session, "HR Executive")
        swe = await _get_or_create_designation(session, "Software Engineer")
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
        if settings.seed_demo_data:
            await _seed_demo_data(
                session,
                departments={"hr": hr_department, "eng": engineering},
                designations={"manager": manager, "hr_exec": hr_exec, "swe": swe},
                leave_types=leave_types,
                today=today,
            )
            await session.commit()
            print("Demo seed data ensured.")
    print("Database bootstrap completed.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
