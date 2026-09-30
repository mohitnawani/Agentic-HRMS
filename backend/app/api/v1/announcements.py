# app/api/v1/announcements.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.announcement import Announcement
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.post("", response_model=AnnouncementRead, dependencies=[Depends(require_permission("announcement:write"))])
async def create_announcement(
    data: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    announcement = Announcement(**data.model_dump(), created_by=current_user.id)
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return announcement


@router.get("", response_model=list[AnnouncementRead], dependencies=[Depends(require_permission("announcement:read"))])
async def list_announcements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Announcement).order_by(Announcement.created_at.desc())
    if current_user.role == RoleEnum.EMPLOYEE:
        stmt = stmt.where(Announcement.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/{announcement_id}", response_model=AnnouncementRead, dependencies=[Depends(require_permission("announcement:write"))])
async def update_announcement(
    announcement_id: uuid.UUID, data: AnnouncementUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(announcement, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update announcement")
    await db.refresh(announcement)
    return announcement


@router.delete("/{announcement_id}", status_code=204, dependencies=[Depends(require_permission("announcement:write"))])
async def delete_announcement(announcement_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    await db.delete(announcement)
    await db.commit()
