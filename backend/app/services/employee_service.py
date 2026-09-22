import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services import leave_service


async def create_employee(db: AsyncSession, data: EmployeeCreate) -> Employee:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=hash_password(data.password),
        role=RoleEnum.EMPLOYEE,
    )
    db.add(user)
    await db.flush()  # get user.id before creating employee

    employee = Employee(
        user_id=user.id,
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        date_of_joining=data.date_of_joining,
        department_id=data.department_id,
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


async def update_employee(db: AsyncSession, employee_id: uuid.UUID, data: EmployeeUpdate) -> Employee:
    employee = await get_employee(db, employee_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    await db.commit()
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