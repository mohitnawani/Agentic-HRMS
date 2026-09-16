import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


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
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
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


async def delete_employee(db: AsyncSession, employee_id: uuid.UUID) -> None:
    employee = await get_employee(db, employee_id)
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.is_active = False  # soft-delete the login, don't hard-delete the account
    await db.delete(employee)
    await db.commit()