import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services import leave_service


async def _ensure_department(db: AsyncSession, department_id: uuid.UUID | None) -> None:
    if department_id is None:
        return
    exists = await db.scalar(select(Department.id).where(Department.id == department_id))
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


async def _ensure_designation(db: AsyncSession, designation_id: uuid.UUID | None) -> Designation | None:
    if designation_id is None:
        return None
    designation = await db.scalar(select(Designation).where(Designation.id == designation_id))
    if designation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designation not found")
    return designation


def _ensure_designation_in_department(
    designation: Designation | None, department_id: uuid.UUID | None
) -> None:
    """A designation always belongs to exactly one department."""
    if designation is not None and department_id is not None:
        if designation.department_id != department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Designation does not belong to the selected department",
            )


def _validate_dates(date_of_birth: date | None, date_of_joining: date | None) -> None:
    today = date.today()
    if date_of_birth is not None and date_of_birth > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date of birth cannot be in the future",
        )
    if (
        date_of_birth is not None
        and date_of_joining is not None
        and date_of_birth >= date_of_joining
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date of birth must be before date of joining",
        )


async def _ensure_employee_code_free(    db: AsyncSession, employee_code: str | None, exclude_id: uuid.UUID | None = None
) -> None:
    if not employee_code:
        return
    stmt = select(Employee.id).where(Employee.employee_code == employee_code)
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    if await db.scalar(stmt) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee code already in use")


async def create_employee(db: AsyncSession, data: EmployeeCreate) -> Employee:
    existing = await db.execute(select(User).where(func.lower(User.email) == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    await _ensure_department(db, data.department_id)
    designation = await _ensure_designation(db, data.designation_id)
    await _ensure_employee_code_free(db, data.employee_code)
    _validate_dates(data.date_of_birth, data.date_of_joining)
    # One primary department + one primary designation; inherit the
    # department from the designation when only it is provided.
    department_id = data.department_id
    if designation is not None:
        if department_id is None:
            department_id = designation.department_id
        _ensure_designation_in_department(designation, department_id)

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    try:
        db.add(user)
        await db.flush()  # get user.id before creating employee

        employee = Employee(
            user_id=user.id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            date_of_joining=data.date_of_joining,
            department_id=department_id,
            designation_id=data.designation_id,
            employee_code=data.employee_code,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            address=data.address,
            city=data.city,
            emergency_contact=data.emergency_contact,
            bank_name=data.bank_name,
            account_number=data.account_number,
            ifsc_code=data.ifsc_code,
            id_proof_type=data.id_proof_type,
            id_proof_number=data.id_proof_number,
        )
        db.add(employee)
        await db.flush()  # get employee.id for the code below
        if not employee.employee_code:
            count_result = await db.execute(select(Employee.id))
            employee.employee_code = f"EMP-{len(count_result.scalars().all()):04d}"
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    await db.refresh(employee)
    await leave_service.initialize_balances_for_employee(db, employee.id)
    return employee


async def list_employees(db: AsyncSession, department_id: uuid.UUID | None = None) -> list[Employee]:
    query = select(Employee)
    if department_id:
        query = query.where(Employee.department_id == department_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_employee(db: AsyncSession, employee_id: uuid.UUID) -> Employee:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


async def get_employee_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Employee:
    result = await db.execute(select(Employee).where(Employee.user_id == user_id))
    employee = result.scalar_one_or_none()
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found")
    return employee


async def update_employee(
    db: AsyncSession, employee_id: uuid.UUID, data: EmployeeUpdate, actor: User
) -> Employee:
    employee = await get_employee(db, employee_id)
    if actor.role == RoleEnum.HR:
        user_result = await db.execute(select(User).where(User.id == employee.user_id))
        target = user_result.scalar_one_or_none()
        if target is None or target.role == RoleEnum.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR cannot edit admin accounts")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    await _ensure_department(db, employee.department_id)
    designation = await _ensure_designation(db, employee.designation_id)
    if designation is not None and employee.department_id is None:
        employee.department_id = designation.department_id
    _ensure_designation_in_department(designation, employee.department_id)
    await _ensure_employee_code_free(db, employee.employee_code, exclude_id=employee.id)
    _validate_dates(employee.date_of_birth, employee.date_of_joining)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update employee")
    await db.refresh(employee)
    return employee


async def delete_employee(db: AsyncSession, employee_id: uuid.UUID, actor: User) -> None:
    employee = await get_employee(db, employee_id)
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    user = user_result.scalar_one_or_none()
    if actor.role == RoleEnum.HR and (user is None or user.role != RoleEnum.EMPLOYEE):
        # HR may delete employees only — never admins, HRs (including self), or orphans
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR can only delete employee accounts")
    if user:
        user.is_active = False  # soft-delete the login, don't hard-delete the account
    # remove rows owned by this employee so the profile delete doesn't violate FKs
    for model in (LeaveRequest, LeaveBalance, Attendance):
        await db.execute(delete(model).where(model.employee_id == employee_id))
    await db.delete(employee)
    await db.commit()


async def set_employee_photo(db: AsyncSession, employee_id: uuid.UUID, photo_url: str) -> Employee:
    employee = await get_employee(db, employee_id)
    employee.photo_url = photo_url
    await db.commit()
    await db.refresh(employee)
    return employee
