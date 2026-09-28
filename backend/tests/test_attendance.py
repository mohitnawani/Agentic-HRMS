import uuid
from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.db.session import async_session
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


async def _create_hr_and_employee(client):
    suffix = uuid.uuid4().hex[:8]
    password = "testpass123"
    async with async_session() as session:
        hr = User(
            email=f"attendance_hr_{suffix}@test.local",
            hashed_password=hash_password(password),
            role=RoleEnum.HR,
        )
        employee_user = User(
            email=f"attendance_employee_{suffix}@test.local",
            hashed_password=hash_password(password),
            role=RoleEnum.EMPLOYEE,
        )
        session.add_all([hr, employee_user])
        await session.flush()
        employee = Employee(
            user_id=employee_user.id,
            first_name="Attendance",
            last_name="Target",
            date_of_joining=datetime.now(UTC).date(),
        )
        session.add(employee)
        await session.commit()
        employee_id = employee.id
        hr_email = hr.email

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": hr_email, "password": password},
    )
    return login.json()["access_token"], employee_id


@pytest.mark.asyncio
async def test_check_in_and_duplicate_blocked(client, employee_token):
    headers = {"Authorization": f"Bearer {employee_token}"}
    first = await client.post("/api/v1/attendance/check-in", headers=headers)
    assert first.status_code == 200

    second = await client.post("/api/v1/attendance/check-in", headers=headers)
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_employee_cannot_correct_attendance(client, employee_token):
    headers = {"Authorization": f"Bearer {employee_token}"}
    resp = await client.patch(
        "/api/v1/attendance/00000000-0000-0000-0000-000000000000/correct",
        json={"correction_reason": "test"}, headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_hr_can_create_and_update_attendance_correction_by_date(client):
    token, employee_id = await _create_hr_and_employee(client)
    headers = {"Authorization": f"Bearer {token}"}
    attendance_date = datetime.now(UTC).date().isoformat()

    created = await client.put(
        f"/api/v1/attendance/{employee_id}/date/{attendance_date}",
        json={"status": "present", "correction_reason": "Missed punch"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "present"

    updated = await client.put(
        f"/api/v1/attendance/{employee_id}/date/{attendance_date}",
        json={"status": "half_day", "correction_reason": "Approved half day"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["status"] == "half_day"


@pytest.mark.asyncio
async def test_hr_can_correct_attendance_through_guided_assistant(client):
    token, employee_id = await _create_hr_and_employee(client)
    headers = {"Authorization": f"Bearer {token}"}
    attendance_date = datetime.now(UTC).date().isoformat()

    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Correct attendance"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert "employee" in first.json()["answer"].lower()
    conversation_id = first.json()["conversation_id"]

    steps = [
        (str(employee_id), {"employee_id": str(employee_id)}, "date"),
        (attendance_date, {"date": attendance_date}, "status"),
        ("Present", {"status": "present"}, "corrected"),
        ("Missed punch", {"correction_reason": "Missed punch"}, "confirm"),
    ]
    for message, parameters, expected in steps:
        response = await client.post(
            "/api/v1/agent/chat",
            json={
                "message": message,
                "conversation_id": conversation_id,
                "parameters": parameters,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert expected in response.json()["answer"].lower()

    confirmed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "confirm", "conversation_id": conversation_id},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert "corrected" in confirmed.json()["answer"].lower()

    history = await client.get(
        f"/api/v1/attendance/{employee_id}", headers=headers
    )
    assert history.status_code == 200
    matching = [row for row in history.json() if row["date"] == attendance_date]
    assert len(matching) == 1
    assert matching[0]["status"] == "present"


@pytest.mark.asyncio
async def test_calendar_grid_shape_and_flags(client, employee_token):
    headers = {"Authorization": f"Bearer {employee_token}"}
    resp = await client.get("/api/v1/attendance/me/calendar", params={"year": 2026, "month": 9}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2026 and body["month"] == 9
    assert len(body["days"]) == 30  # September has 30 days

    by_date = {d["date"]: d for d in body["days"]}
    # 2026-09-05 is a Saturday, 2026-09-06 a Sunday
    assert by_date["2026-09-05"]["is_weekend"] is True
    assert by_date["2026-09-06"]["is_weekend"] is True
    assert by_date["2026-09-07"]["is_weekend"] is False
    # fixture employee joined "today", so all of Sept 1 is pre-joining and blank
    assert by_date["2026-09-01"]["before_joining"] is True
    assert by_date["2026-09-01"]["state"] == "before_joining"
