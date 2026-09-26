import uuid

from pydantic import BaseModel

from app.models.role import RoleEnum
from app.schemas.common import EmailT, PasswordT


class UserCreateByAdmin(BaseModel):
    email: EmailT
    password: PasswordT
    role: RoleEnum

class UserAdminRead(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True
