import uuid
from datetime import date

import pytest
import pytest_asyncio

from app.core.security import hash_password
from app.db.session import async_session
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


@pytest_asyncio.fixture
async def hr_token(client):
    async with async_session() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"hr_{uuid.uuid4().hex[:6]}@test.local",
            hashed_password=hash_password("testpass123"),
            role=RoleEnum.HR,
        )
        session.add(user)
        await session.flush()
        session.add(
            Employee(
                user_id=user.id,
                first_name="HR",
                last_name="Tester",
                date_of_joining=date.today(),
            )
        )
        await session.commit()
        email = user.email

    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    return resp.json()["access_token"]


def _holiday_payload():
    return {"name": f"TestDay-{uuid.uuid4().hex[:6]}", "date": str(date.today())}


# --- holidays ---

@pytest.mark.asyncio
async def test_holiday_crud(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post("/api/v1/holidays", json=_holiday_payload(), headers=h)
    assert create.status_code == 200
    hid = create.json()["id"]

    dup = await client.post(
        "/api/v1/holidays",
        json={"name": create.json()["name"], "date": create.json()["date"]},
        headers=h,
    )
    assert dup.status_code == 400

    listed = await client.get("/api/v1/holidays", headers=h)
    assert any(x["id"] == hid for x in listed.json())

    patched = await client.patch(f"/api/v1/holidays/{hid}", json={"name": "Renamed"}, headers=h)
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"

    assert (await client.delete(f"/api/v1/holidays/{hid}", headers=h)).status_code == 204
    assert (await client.patch(f"/api/v1/holidays/{hid}", json={"name": "x"}, headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_holiday_permissions(client, admin_token, employee_token, hr_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_emp = {"Authorization": f"Bearer {employee_token}"}
    h_hr = {"Authorization": f"Bearer {hr_token}"}

    assert (await client.get("/api/v1/holidays", headers=h_emp)).status_code == 200
    assert (await client.get("/api/v1/holidays", headers=h_hr)).status_code == 200
    assert (await client.post("/api/v1/holidays", json=_holiday_payload(), headers=h_emp)).status_code == 403
    assert (await client.post("/api/v1/holidays", json=_holiday_payload(), headers=h_hr)).status_code == 403
    assert (await client.post("/api/v1/holidays", json=_holiday_payload(), headers=h_admin)).status_code == 200


@pytest.mark.asyncio
async def test_holiday_year_filter(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    payload = _holiday_payload()
    hid = (await client.post("/api/v1/holidays", json=payload, headers=h)).json()["id"]
    year = date.today().year
    in_year = await client.get(f"/api/v1/holidays?year={year}", headers=h)
    assert any(x["id"] == hid for x in in_year.json())
    out_year = await client.get(f"/api/v1/holidays?year={year + 5}", headers=h)
    assert all(x["id"] != hid for x in out_year.json())


# --- announcements ---

@pytest.mark.asyncio
async def test_announcement_crud(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    title = f"Notice-{uuid.uuid4().hex[:6]}"
    create = await client.post(
        "/api/v1/announcements", json={"title": title, "body": "All hands Friday"}, headers=h
    )
    assert create.status_code == 200
    assert create.json()["created_by"] is not None
    aid = create.json()["id"]

    listed = await client.get("/api/v1/announcements", headers=h)
    assert any(x["id"] == aid for x in listed.json())

    patched = await client.patch(
        f"/api/v1/announcements/{aid}", json={"is_active": False}, headers=h
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    assert (await client.delete(f"/api/v1/announcements/{aid}", headers=h)).status_code == 204


@pytest.mark.asyncio
async def test_announcement_permissions(client, employee_token, hr_token):
    h_emp = {"Authorization": f"Bearer {employee_token}"}
    h_hr = {"Authorization": f"Bearer {hr_token}"}

    assert (await client.get("/api/v1/announcements", headers=h_emp)).status_code == 200
    denied = await client.post(
        "/api/v1/announcements",
        json={"title": f"x-{uuid.uuid4().hex[:6]}", "body": "y"},
        headers=h_emp,
    )
    assert denied.status_code == 403

    allowed = await client.post(
        "/api/v1/announcements",
        json={"title": f"HR-{uuid.uuid4().hex[:6]}", "body": "from HR"},
        headers=h_hr,
    )
    assert allowed.status_code == 200
