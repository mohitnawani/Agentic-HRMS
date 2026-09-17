from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import AdminDashboard, EmployeeDashboard, HRDashboard
from app.services import dashboard_service, employee_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/employee", response_model=EmployeeDashboard, dependencies=[Depends(require_permission("employee:read_self"))])
async def employee_dashboard(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    employee = await employee_service.get_employee_by_user_id(db, current_user.id)
    return await dashboard_service.employee_dashboard(db, employee.id)


@router.get("/hr", response_model=HRDashboard, dependencies=[Depends(require_permission("leave:read_all"))])
async def hr_dashboard(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.hr_dashboard(db)


@router.get("/admin", response_model=AdminDashboard, dependencies=[Depends(require_permission("user:manage"))])
async def admin_dashboard(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.admin_dashboard(db)