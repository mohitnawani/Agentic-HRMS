from fastapi import APIRouter

from app.api.v1 import auth, employees

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(employees.router)
# individual routers (auth, employees, departments, etc.) get included here
# as you build them in Week 1 — leave empty for now, health check lives in main.py