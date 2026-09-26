import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.role import RoleEnum
from app.schemas.common import BlankableStr, EmailT, PasswordT, PhoneT, StrippedStr

# Trimmed name (1-100 to match the column size).
NameT = Annotated[StrippedStr, Field(min_length=1, max_length=100)]
# Optional short text that becomes None when blank.
OptText100 = Annotated[BlankableStr, Field(max_length=100)]


class EmployeeCreate(BaseModel):
    email: EmailT
    password: PasswordT
    first_name: NameT
    last_name: NameT
    phone: PhoneT | None = None
    date_of_joining: date
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    role: RoleEnum = RoleEnum.EMPLOYEE
    employee_code: Annotated[BlankableStr, Field(max_length=20)] = None
    date_of_birth: date | None = None
    gender: OptText100 = None
    address: Annotated[BlankableStr, Field(max_length=500)] = None
    city: OptText100 = None
    emergency_contact: PhoneT | None = None
    bank_name: OptText100 = None
    account_number: Annotated[BlankableStr, Field(max_length=50)] = None
    ifsc_code: Annotated[BlankableStr, Field(max_length=20)] = None
    id_proof_type: Annotated[BlankableStr, Field(max_length=50)] = None
    id_proof_number: Annotated[BlankableStr, Field(max_length=100)] = None


class EmployeeUpdate(BaseModel):
    first_name: NameT | None = None
    last_name: NameT | None = None
    phone: PhoneT | None = None
    date_of_joining: date | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employee_code: Annotated[BlankableStr, Field(max_length=20)] = None
    date_of_birth: date | None = None
    gender: OptText100 = None
    address: Annotated[BlankableStr, Field(max_length=500)] = None
    city: OptText100 = None
    emergency_contact: PhoneT | None = None
    bank_name: OptText100 = None
    account_number: Annotated[BlankableStr, Field(max_length=50)] = None
    ifsc_code: Annotated[BlankableStr, Field(max_length=20)] = None
    id_proof_type: Annotated[BlankableStr, Field(max_length=50)] = None
    id_proof_number: Annotated[BlankableStr, Field(max_length=100)] = None


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
