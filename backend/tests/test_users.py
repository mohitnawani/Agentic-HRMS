import uuid

import pytest


def _new_user_payload(role="hr"):
    return {
        "email": f"managed_{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
        "role": role,
        "first_name": "Managed",
        "last_name": "User",
    }


@pytest.mark.asyncio
async def test_admin_create_user_and_login(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    created = await client.post("/api/v1/users", json=_new_user_payload(), headers=h)
    assert created.status_code == 200
    assert created.json()["role"] == "hr"
    assert created.json()["is_active"] is True

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": created.json()["email"], "password": "testpass123"},
    )
    assert login.status_code == 200

    dup = await client.post("/api/v1/users", json={
        "email": created.json()["email"], "password": "x", "role": "hr",
    }, headers=h)
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_employee_cannot_manage_users(client, employee_token):
    h = {"Authorization": f"Bearer {employee_token}"}
    assert (await client.post("/api/v1/users", json=_new_user_payload(), headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_deactivate_blocks_login_and_reactivate_restores(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    payload = _new_user_payload(role="employee")
    uid = (await client.post("/api/v1/users", json=payload, headers=h)).json()["id"]

    off = await client.patch(f"/api/v1/users/{uid}/deactivate", headers=h)
    assert off.status_code == 200
    assert off.json()["is_active"] is False
    assert (await client.post(
        "/api/v1/auth/login", data={"username": payload["email"], "password": "testpass123"}
    )).status_code == 403

    on = await client.patch(f"/api/v1/users/{uid}/activate", headers=h)
    assert on.json()["is_active"] is True
    assert (await client.post(
        "/api/v1/auth/login", data={"username": payload["email"], "password": "testpass123"}
    )).status_code == 200


@pytest.mark.asyncio
async def test_activate_missing_user_404(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    assert (await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/activate", headers=h
    )).status_code == 404


@pytest.mark.asyncio
async def test_admin_list_users_and_employee_forbidden(client, admin_token, employee_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_emp = {"Authorization": f"Bearer {employee_token}"}

    created = await client.post("/api/v1/users", json=_new_user_payload(), headers=h_admin)
    assert created.status_code == 200

    listed = await client.get("/api/v1/users", headers=h_admin)
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
    assert any(u["id"] == created.json()["id"] for u in listed.json())

    assert (await client.get("/api/v1/users", headers=h_emp)).status_code == 403


@pytest.mark.asyncio
async def test_cannot_deactivate_self(client, admin_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    payload = _new_user_payload(role="admin")
    created = await client.post("/api/v1/users", json=payload, headers=h_admin)
    uid = created.json()["id"]
    login = await client.post(
        "/api/v1/auth/login", data={"username": payload["email"], "password": "testpass123"}
    )
    h_self = {"Authorization": f"Bearer {login.json()['access_token']}"}
    denied = await client.patch(f"/api/v1/users/{uid}/deactivate", headers=h_self)
    assert denied.status_code == 400
    # still active afterwards
    listed = await client.get("/api/v1/users", headers=h_admin)
    assert next(u for u in listed.json() if u["id"] == uid)["is_active"] is True


@pytest.mark.asyncio
async def test_hr_create_rules(client, admin_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    hr_payload = _new_user_payload(role="hr")
    hr_created = await client.post("/api/v1/users", json=hr_payload, headers=h_admin)
    assert hr_created.status_code == 200
    hr_login = await client.post(
        "/api/v1/auth/login", data={"username": hr_payload["email"], "password": "testpass123"}
    )
    h_hr = {"Authorization": f"Bearer {hr_login.json()['access_token']}"}

    # HR can create HR and employee accounts...
    assert (await client.post("/api/v1/users", json=_new_user_payload(role="hr"), headers=h_hr)).status_code == 200
    assert (await client.post("/api/v1/users", json=_new_user_payload(role="employee"), headers=h_hr)).status_code == 200
    # ...but never admins
    assert (await client.post("/api/v1/users", json=_new_user_payload(role="admin"), headers=h_hr)).status_code == 403
    # admin can create admins
    assert (await client.post("/api/v1/users", json=_new_user_payload(role="admin"), headers=h_admin)).status_code == 200
