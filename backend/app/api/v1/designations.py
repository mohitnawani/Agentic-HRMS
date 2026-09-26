# app/api/v1/designations.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.schemas.designation import DesignationCreate, DesignationRead, DesignationUpdate

router = APIRouter(prefix="/designations", tags=["designations"])


def _to_read(desig: Designation, department_name: str | None) -> DesignationRead:
    return DesignationRead(
        id=desig.id,
        title=desig.title,
        department_id=desig.department_id,
        department_name=department_name,
    )


async def _title_taken(db: AsyncSession, title: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Designation.id).where(func.lower(Designation.title) == title.lower())
    if exclude_id is not None:
        stmt = stmt.where(Designation.id != exclude_id)
    return await db.scalar(stmt) is not None


async def _get_department_or_404(db: AsyncSession, department_id: uuid.UUID) -> Department:
    dept = await db.scalar(select(Department).where(Department.id == department_id))
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


@router.post("", response_model=DesignationRead, dependencies=[Depends(require_permission("designation:write"))])
async def create_designation(data: DesignationCreate, db: AsyncSession = Depends(get_db)):
    dept = await _get_department_or_404(db, data.department_id)
    if await _title_taken(db, data.title):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    desig = Designation(title=data.title, department_id=data.department_id)
    db.add(desig)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    await db.refresh(desig)
    return _to_read(desig, dept.name)


@router.get("", response_model=list[DesignationRead], dependencies=[Depends(require_permission("designation:read"))])
async def list_designations(
    department_id: uuid.UUID | None = Query(None), db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Designation, Department.name)
        .join(Department, Department.id == Designation.department_id)
        .order_by(Department.name, Designation.title)
    )
    if department_id is not None:
        stmt = stmt.where(Designation.department_id == department_id)
    rows = (await db.execute(stmt)).all()
    return [_to_read(desig, dept_name) for desig, dept_name in rows]


@router.patch("/{designation_id}", response_model=DesignationRead, dependencies=[Depends(require_permission("designation:write"))])
async def update_designation(designation_id: uuid.UUID, data: DesignationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Designation).where(Designation.id == designation_id))
    desig = result.scalar_one_or_none()
    if desig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designation not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(desig, field, value)
    if data.department_id is not None:
        await _get_department_or_404(db, desig.department_id)
        in_use = await db.scalar(
            select(Employee.id).where(Employee.designation_id == desig.id).limit(1)
        )
        if in_use is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move a designation that employees currently use",
            )
    if data.title is not None and await _title_taken(db, desig.title, exclude_id=desig.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    await db.refresh(desig)
    dept_name = await db.scalar(select(Department.name).where(Department.id == desig.department_id))
    return _to_read(desig, dept_name)


@router.delete("/{designation_id}", status_code=204, dependencies=[Depends(require_permission("designation:write"))])
async def delete_designation(designation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Designation).where(Designation.id == designation_id))
    desig = result.scalar_one_or_none()
    if desig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designation not found")
    await db.delete(desig)
    await db.commit()
