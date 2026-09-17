import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def leave_type(client, admin_token):
    resp = await client.post(
        "/api/v1/leave/types",
        json={"name": f"Casual-{uuid.uuid4().hex[:6]}", "default_annual_days": 12},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest_asyncio.fixture
async def employee_auth(client, admin_token):
    email = f"leave_{uuid.uuid4().hex[:6]}@example.com"
    create = await client.post(
        "/api/v1/employees",
        json={
            "email": email, "password": "testpass123",
            "first_name": "Leave", "last_name": "Tester",
            "date_of_joining": str(date.today()),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create.status_code == 200
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    assert login.status_code == 200
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}, "email": email}


def _two_day_window():
    start = date.today()
    return str(start), str(start + timedelta(days=1))


@pytest.mark.asyncio
async def test_balances_auto_initialized(client, leave_type, employee_auth):
    resp = await client.get("/api/v1/leave/balance", headers=employee_auth["headers"])
    assert resp.status_code == 200
    entry = next(b for b in resp.json() if b["leave_type_id"] == leave_type["id"])
    assert entry["used_days"] == 0
    assert entry["remaining_days"] == entry["total_days"] == 12


@pytest.mark.asyncio
async def test_apply_approve_decrements_balance(client, admin_token, leave_type, employee_auth):
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    start, end = _two_day_window()
    apply = await client.post(
        "/api/v1/leave/requests",
        json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end, "reason": "test"},
        headers=employee_auth["headers"],
    )
    assert apply.status_code == 200
    assert apply.json()["status"] == "pending"
    req_id = apply.json()["id"]

    mine = await client.get("/api/v1/leave/requests/me", headers=employee_auth["headers"])
    assert any(r["id"] == req_id for r in mine.json())

    pending = await client.get("/api/v1/leave/requests/pending", headers=admin_h)
    assert any(r["id"] == req_id for r in pending.json())

    approve = await client.post(f"/api/v1/leave/requests/{req_id}/approve", headers=admin_h)
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    bal = await client.get("/api/v1/leave/balance", headers=employee_auth["headers"])
    entry = next(b for b in bal.json() if b["leave_type_id"] == leave_type["id"])
    assert entry["used_days"] == 2
    assert entry["remaining_days"] == 10


@pytest.mark.asyncio
async def test_employee_cannot_approve(client, leave_type, employee_auth):
    start, end = _two_day_window()
    apply = await client.post(
        "/api/v1/leave/requests",
        json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end, "reason": "test"},
        headers=employee_auth["headers"],
    )
    req_id = apply.json()["id"]
    denied = await client.post(f"/api/v1/leave/requests/{req_id}/approve", headers=employee_auth["headers"])
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_cancel_only_pending(client, admin_token, leave_type, employee_auth):
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    start, end = _two_day_window()

    first = await client.post(
        "/api/v1/leave/requests",
        json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end, "reason": "cancel me"},
        headers=employee_auth["headers"],
    )
    cancelled = await client.post(f"/api/v1/leave/requests/{first.json()['id']}/cancel", headers=employee_auth["headers"])
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    second = await client.post(
        "/api/v1/leave/requests",
        json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end, "reason": "approve me"},
        headers=employee_auth["headers"],
    )
    await client.post(f"/api/v1/leave/requests/{second.json()['id']}/approve", headers=admin_h)
    late_cancel = await client.post(
        f"/api/v1/leave/requests/{second.json()['id']}/cancel", headers=employee_auth["headers"]
    )
    assert late_cancel.status_code == 400
