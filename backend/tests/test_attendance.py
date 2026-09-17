import pytest


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