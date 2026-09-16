from fastapi import APIRouter

from app.api.v1 import auth, departments, designations, employees

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(departments.router)
api_router.include_router(designations.router)