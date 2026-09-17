import uuid
from pydantic import BaseModel, EmailStr
from app.models.role import RoleEnum

class UserCreateByAdmin(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum

class UserAdminRead(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleEnum
    is_active: bool
    class Config:
        from_attributes = True