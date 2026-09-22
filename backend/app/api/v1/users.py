# app/api/v1/users.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_permission("user:manage"))])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, dependencies=[Depends(require_permission("user:manage"))])
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    if data.first_name and data.last_name:
        db.add(Employee(
            user_id=user.id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_joining=date.today(),
        ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    await db.refresh(user)
    return user


async def _set_active(db: AsyncSession, user_id: uuid.UUID, active: bool) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = active
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserRead, dependencies=[Depends(require_permission("user:manage"))])
async def activate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_active(db, user_id, True)


@router.patch("/{user_id}/deactivate", response_model=UserRead, dependencies=[Depends(require_permission("user:manage"))])
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_active(db, user_id, False)
