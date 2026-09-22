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
    employee_code: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    city: str | None = None
    emergency_contact: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    id_proof_type: str | None = None
    id_proof_number: str | None = None


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    date_of_joining: date | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employee_code: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    city: str | None = None
    emergency_contact: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    id_proof_type: str | None = None
    id_proof_number: str | None = None


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
    photo_url: str | None = None
    is_active: bool = True
    employee_code: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    city: str | None = None
    emergency_contact: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    id_proof_type: str | None = None
    id_proof_number: str | None = None

    class Config:
        from_attributes = True