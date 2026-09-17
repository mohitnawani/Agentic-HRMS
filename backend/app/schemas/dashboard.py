from pydantic import BaseModel


class EmployeeDashboard(BaseModel):
    attendance_this_month: dict
    leave_balances: list[dict]
    pending_leave_requests: int


class HRDashboard(BaseModel):
    total_employees: int
    on_leave_today: int
    pending_approvals: int
    department_breakdown: dict[str, int]


class AdminDashboard(BaseModel):
    total_employees: int
    total_departments: int
    active_users: int
    department_breakdown: dict[str, int]