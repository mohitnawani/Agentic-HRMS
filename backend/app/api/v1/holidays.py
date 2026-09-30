# app/api/v1/holidays.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.holiday import Holiday
from app.schemas.holiday import HolidayCreate, HolidayRead, HolidayUpdate

router = APIRouter(prefix="/holidays", tags=["holidays"])


async def _holiday_taken(
    db: AsyncSession, name: str, day: date, exclude_id: uuid.UUID | None = None
) -> bool:
    stmt = select(Holiday.id).where(
        func.lower(Holiday.name) == name.lower(), Holiday.date == day
    )
    if exclude_id is not None:
        stmt = stmt.where(Holiday.id != exclude_id)
    return await db.scalar(stmt) is not None


@router.post("", response_model=HolidayRead, dependencies=[Depends(require_permission("holiday:write"))])
async def create_holiday(data: HolidayCreate, db: AsyncSession = Depends(get_db)):
    if await _holiday_taken(db, data.name, data.date):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holiday already exists")
    holiday = Holiday(**data.model_dump())
    db.add(holiday)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holiday already exists")
    await db.refresh(holiday)
    return holiday


@router.get("", response_model=list[HolidayRead], dependencies=[Depends(require_permission("holiday:read"))])
async def list_holidays(
    year: int | None = Query(None, ge=2000, le=2100), db: AsyncSession = Depends(get_db),
):
    query = select(Holiday)
    if year:
        query = query.where(Holiday.date >= date(year, 1, 1), Holiday.date < date(year + 1, 1, 1))
    result = await db.execute(query.order_by(Holiday.date))
    return list(result.scalars().all())


@router.patch("/{holiday_id}", response_model=HolidayRead, dependencies=[Depends(require_permission("holiday:write"))])
async def update_holiday(holiday_id: uuid.UUID, data: HolidayUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    holiday = result.scalar_one_or_none()
    if holiday is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(holiday, field, value)
    if await _holiday_taken(db, holiday.name, holiday.date, exclude_id=holiday.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holiday already exists")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holiday already exists")
    await db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=204, dependencies=[Depends(require_permission("holiday:write"))])
async def delete_holiday(holiday_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    holiday = result.scalar_one_or_none()
    if holiday is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    await db.delete(holiday)
    await db.commit()
