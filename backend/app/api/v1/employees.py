import uuid

import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.services import employee_service
from app.services import policy_service as cloudinary_gate

router = APIRouter(prefix="/employees", tags=["employees"])


def _to_read_schema(employee, user: User) -> EmployeeRead:
    return EmployeeRead(
        id=employee.id,
        user_id=employee.user_id,
        email=user.email,
        role=user.role.value,
        first_name=employee.first_name,
        last_name=employee.last_name,
        phone=employee.phone,
        date_of_joining=employee.date_of_joining,
        department_id=employee.department_id,
        designation_id=employee.designation_id,
        photo_url=employee.photo_url,
        is_active=user.is_active,
        employee_code=employee.employee_code,
        date_of_birth=employee.date_of_birth,
        gender=employee.gender,
        address=employee.address,
        city=employee.city,
        emergency_contact=employee.emergency_contact,
        bank_name=employee.bank_name,
        account_number=employee.account_number,
        ifsc_code=employee.ifsc_code,
        id_proof_type=employee.id_proof_type,
        id_proof_number=employee.id_proof_number,
    )


@router.post("", response_model=EmployeeRead, dependencies=[Depends(require_permission("employee:create"))])
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    employee = await employee_service.create_employee(db, data)
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    return _to_read_schema(employee, user_result.scalar_one())


@router.get("", response_model=list[EmployeeRead], dependencies=[Depends(require_permission("employee:read_all"))])
async def list_employees(department_id: uuid.UUID | None = Query(None), db: AsyncSession = Depends(get_db)):
    employees = await employee_service.list_employees(db, department_id)
    results = []
    for emp in employees:
        user_result = await db.execute(select(User).where(User.id == emp.user_id))
        results.append(_to_read_schema(emp, user_result.scalar_one()))
    return results


@router.get("/me", response_model=EmployeeRead, dependencies=[Depends(require_permission("employee:read_self"))])
async def get_my_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return _to_read_schema(employee, current_user)


@router.get("/{employee_id}", response_model=EmployeeRead, dependencies=[Depends(require_permission("employee:read_all"))])
async def get_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee(db, employee_id)
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    return _to_read_schema(employee, user_result.scalar_one())


@router.patch("/{employee_id}", response_model=EmployeeRead, dependencies=[Depends(require_permission("employee:update"))])
async def update_employee(employee_id: uuid.UUID, data: EmployeeUpdate, db: AsyncSession = Depends(get_db)):
    employee = await employee_service.update_employee(db, employee_id, data)
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    return _to_read_schema(employee, user_result.scalar_one())


@router.delete("/{employee_id}", status_code=204, dependencies=[Depends(require_permission("employee:delete"))])
async def delete_employee(
    employee_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await employee_service.delete_employee(db, employee_id, current_user)


@router.post("/{employee_id}/photo", response_model=EmployeeRead, dependencies=[Depends(require_permission("employee:update"))])
async def upload_employee_photo(
    employee_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files allowed")
    cloudinary_gate._ensure_configured()

    contents = await file.read()
    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="hrms/employees",
            resource_type="image",
            public_id=f"{uuid.uuid4()}_{file.filename}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cloudinary upload failed: {exc}"
        )
    employee = await employee_service.set_employee_photo(db, employee_id, result["secure_url"])
    user_result = await db.execute(select(User).where(User.id == employee.user_id))
    return _to_read_schema(employee, user_result.scalar_one())