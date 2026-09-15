import asyncio
import uuid
from datetime import date

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


async def _get_or_create_department(session, name: str) -> Department:
    result = await session.execute(select(Department).where(Department.name == name))
    dept = result.scalar_one_or_none()
    if dept is None:
        dept = Department(name=name)
        session.add(dept)
        await session.flush()
    return dept


async def _get_or_create_designation(session, title: str) -> Designation:
    result = await session.execute(select(Designation).where(Designation.title == title))
    desig = result.scalar_one_or_none()
    if desig is None:
        desig = Designation(title=title)
        session.add(desig)
        await session.flush()
    return desig


async def _get_or_create_user(session, email: str, password: str, role: RoleEnum) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            role=role,
        )
        session.add(user)
        await session.flush()
    return user


async def _get_or_create_employee(
    session,
    user: User,
    first_name: str,
    last_name: str,
    department_id,
    designation_id,
) -> Employee:
    result = await session.execute(select(Employee).where(Employee.user_id == user.id))
    employee = result.scalar_one_or_none()
    if employee is None:
        employee = Employee(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            date_of_joining=date.today(),
            department_id=department_id,
            designation_id=designation_id,
        )
        session.add(employee)
        await session.flush()
    return employee


async def seed():
    async with async_session() as session:
        dept_eng = await _get_or_create_department(session, "Engineering")
        dept_hr = await _get_or_create_department(session, "Human Resources")

        desig_swe = await _get_or_create_designation(session, "Software Engineer")
        desig_hrx = await _get_or_create_designation(session, "HR Executive")
        desig_mgr = await _get_or_create_designation(session, "Manager")

        admin_user = await _get_or_create_user(
            session, "admin@hrms.local", "admin123", RoleEnum.ADMIN
        )
        employee_user = await _get_or_create_user(
            session, "employee@hrms.local", "employee123", RoleEnum.EMPLOYEE
        )

        await _get_or_create_employee(
            session, admin_user, "Admin", "User", dept_hr.id, desig_mgr.id
        )
        await _get_or_create_employee(
            session, employee_user, "Test", "Employee", dept_eng.id, desig_swe.id
        )

        await session.commit()
        print("Seed complete: 2 users, 2 departments, 3 designations.")


if __name__ == "__main__":
    asyncio.run(seed())
