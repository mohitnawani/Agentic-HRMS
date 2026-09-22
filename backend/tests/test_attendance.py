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