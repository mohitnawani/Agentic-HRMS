import asyncio
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.security import hash_password
from app.db.session import async_session
from app.main import app
from app.models.role import RoleEnum
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_token(client):
    async with async_session() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"admin_{uuid.uuid4().hex[:6]}@test.local",
            hashed_password=hash_password("testpass123"),
            role=RoleEnum.ADMIN,
        )
        session.add(user)
        await session.commit()
        email = user.email

    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def employee_token(client):
    async with async_session() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"emp_{uuid.uuid4().hex[:6]}@test.local",
            hashed_password=hash_password("testpass123"),
            role=RoleEnum.EMPLOYEE,
        )
        session.add(user)
        await session.commit()
        email = user.email

    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    return resp.json()["access_token"]