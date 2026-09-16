import pytest


@pytest.mark.asyncio
async def test_login_success(client, admin_token):
    assert admin_token is not None


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/v1/auth/login", data={"username": "nobody@test.local", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    resp = await client.get("/api/v1/employees/me")
    assert resp.status_code == 401