import pytest


@pytest.mark.asyncio
async def test_employee_cannot_list_all_employees(client, employee_token):
    resp = await client.get("/api/v1/employees", headers={"Authorization": f"Bearer {employee_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_all_employees(client, admin_token):
    resp = await client.get("/api/v1/employees", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200