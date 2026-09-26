# app/api/v1/users.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.user import UserCreate, UserEmailUpdate, UserRead
from app.services import leave_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_permission("user:manage"))])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, dependencies=[Depends(require_permission("user:create"))])
async def create_user(
    data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.role == RoleEnum.ADMIN and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create admin accounts")
    existing = await db.execute(select(User).where(func.lower(User.email) == data.email))
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
    profile = None
    if data.first_name and data.last_name:
        profile = Employee(
            user_id=user.id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_joining=date.today(),
        )
        db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if profile is not None:
        await leave_service.initialize_balances_for_employee(db, profile.id)
    await db.refresh(user)
    return user


async def _set_active(
    db: AsyncSession, user_id: uuid.UUID, active: bool, actor: User
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not active:
        if user.id == actor.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
        if user.role == RoleEnum.ADMIN:
            remaining = await db.execute(
                select(User.id).where(User.role == RoleEnum.ADMIN, User.is_active == True, User.id != user.id).limit(1)  # noqa: E712
            )
            if remaining.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate the last active admin"
                )
    user.is_active = active
    await db.commit()
    await db.refresh(user)
    return user


@router.patch(
    "/{user_id}/email",
    response_model=UserRead,
    dependencies=[Depends(require_permission("user:manage"))],
)
async def update_user_email(
    user_id: uuid.UUID,
    data: UserEmailUpdate,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    duplicate = await db.scalar(
        select(User.id).where(
            func.lower(User.email) == data.email,
            User.id != user_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user.email = data.email
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    await db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserRead, dependencies=[Depends(require_permission("user:manage"))])
async def activate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _set_active(db, user_id, True, current_user)


@router.patch("/{user_id}/deactivate", response_model=UserRead, dependencies=[Depends(require_permission("user:manage"))])
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _set_active(db, user_id, False, current_user)
