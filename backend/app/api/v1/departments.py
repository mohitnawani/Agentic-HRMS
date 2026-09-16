# app/api/v1/departments.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentRead, dependencies=[Depends(require_permission("department:write"))])
async def create_department(data: DepartmentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Department).where(Department.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department already exists")
    dept = Department(**data.model_dump())
    db.add(dept)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department already exists")
    await db.refresh(dept)
    return dept


@router.get("", response_model=list[DepartmentRead], dependencies=[Depends(require_permission("department:read"))])
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department))
    return list(result.scalars().all())


@router.patch("/{department_id}", response_model=DepartmentRead, dependencies=[Depends(require_permission("department:write"))])
async def update_department(department_id: uuid.UUID, data: DepartmentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department already exists")
    await db.refresh(dept)
    return dept


@router.delete("/{department_id}", status_code=204, dependencies=[Depends(require_permission("department:write"))])
async def delete_department(department_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    await db.delete(dept)
    await db.commit()