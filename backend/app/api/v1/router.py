from fastapi import APIRouter

from app.api.v1 import (
    agent,
    announcements,
    attendance,
    auth,
    dashboard,
    departments,
    designations,
    employees,
    holidays,
    leave,
    policies,
    rag,
    users,
)

api_router = APIRouter()
api_router.include_router(agent.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(departments.router)
api_router.include_router(designations.router)
api_router.include_router(attendance.router)
api_router.include_router(leave.router)
api_router.include_router(holidays.router)
api_router.include_router(announcements.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(policies.router)
api_router.include_router(rag.router)
