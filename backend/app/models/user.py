import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.role import RoleEnum

if TYPE_CHECKING:
    from app.models.employee import Employee


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(
        SAEnum(RoleEnum, name="role_enum"), nullable=False, default=RoleEnum.EMPLOYEE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    employee: Mapped["Employee"] = relationship(back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"