# app/api/v1/designations.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.designation import Designation
from app.schemas.designation import DesignationCreate, DesignationRead, DesignationUpdate

router = APIRouter(prefix="/designations", tags=["designations"])


@router.post("", response_model=DesignationRead, dependencies=[Depends(require_permission("designation:write"))])
async def create_designation(data: DesignationCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Designation).where(Designation.title == data.title))
    if existing.scalar_one_or_none():
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
