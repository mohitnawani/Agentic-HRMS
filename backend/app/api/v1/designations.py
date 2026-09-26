# app/api/v1/designations.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.designation import Designation
from app.schemas.designation import DesignationCreate, DesignationRead, DesignationUpdate

router = APIRouter(prefix="/designations", tags=["designations"])


async def _title_taken(db: AsyncSession, title: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Designation.id).where(func.lower(Designation.title) == title.lower())
    if exclude_id is not None:
        stmt = stmt.where(Designation.id != exclude_id)
    return await db.scalar(stmt) is not None


@router.post("", response_model=DesignationRead, dependencies=[Depends(require_permission("designation:write"))])
async def create_designation(data: DesignationCreate, db: AsyncSession = Depends(get_db)):
    if await _title_taken(db, data.title):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    desig = Designation(**data.model_dump())
    db.add(desig)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    await db.refresh(desig)
    return desig


@router.get("", response_model=list[DesignationRead], dependencies=[Depends(require_permission("designation:read"))])
async def list_designations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Designation))
    return list(result.scalars().all())


@router.patch("/{designation_id}", response_model=DesignationRead, dependencies=[Depends(require_permission("designation:write"))])
async def update_designation(designation_id: uuid.UUID, data: DesignationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Designation).where(Designation.id == designation_id))
    desig = result.scalar_one_or_none()
    if desig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designation not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(desig, field, value)
    if data.title is not None and await _title_taken(db, desig.title, exclude_id=desig.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Designation already exists")
    await db.refresh(desig)
    return desig


@router.delete("/{designation_id}", status_code=204, dependencies=[Depends(require_permission("designation:write"))])
async def delete_designation(designation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Designation).where(Designation.id == designation_id))
    desig = result.scalar_one_or_none()
    if desig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designation not found")
    await db.delete(desig)
    await db.commit()
