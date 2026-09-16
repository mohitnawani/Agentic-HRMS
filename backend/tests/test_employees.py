import uuid

import pytest


@pytest.mark.asyncio
async def test_create_and_fetch_employee(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    email = f"newhire_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": email,
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "Hire",
        "date_of_joining": "2026-09-15",
    }
    create_resp = await client.post("/api/v1/employees", json=payload, headers=headers)
    assert create_resp.status_code == 200
    employee_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/employees/{employee_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == email