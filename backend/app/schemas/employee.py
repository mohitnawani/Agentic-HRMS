import uuid
from datetime import date

from pydantic import BaseModel, EmailStr


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: str | None = None
    date_of_joining: date
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None


class EmployeeRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: str
    first_name: str
    last_name: str
    phone: str | None
    date_of_joining: date
    department_id: uuid.UUID | None
    designation_id: uuid.UUID | None

    class Config:
        from_attributes = True