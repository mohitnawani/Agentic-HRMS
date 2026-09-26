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


@pytest.mark.asyncio
async def test_employee_email_is_normalized_and_unique_case_insensitively(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    local_part = f"emailcase_{uuid.uuid4().hex[:6]}"
    mixed_case_email = f"  {local_part.upper()}@GMAIL.COM  "
    payload = {
        "email": mixed_case_email,
        "password": "testpass123",
        "first_name": "Email",
        "last_name": "Case",
        "date_of_joining": "2026-09-15",
    }

    created = await client.post("/api/v1/employees", json=payload, headers=headers)
    assert created.status_code == 200
    assert created.json()["email"] == f"{local_part}@gmail.com"

    duplicate = await client.post(
        "/api/v1/employees",
        json={**payload, "email": f"{local_part}@gmail.com"},
        headers=headers,
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"

    employee_id = created.json()["id"]
    assert (await client.delete(f"/api/v1/employees/{employee_id}", headers=headers)).status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "email",
    [
        "plainaddress",
        "name@",
        "@gmail.com",
        ".name@gmail.com",
        "name..dots@gmail.com",
        "name@gmail",
        "name@-gmail.com",
        123,
    ],
)
async def test_employee_rejects_invalid_email(client, admin_token, email):
    response = await client.post(
        "/api/v1/employees",
        json={
            "email": email,
            "password": "testpass123",
            "first_name": "Invalid",
            "last_name": "Email",
            "date_of_joining": "2026-09-15",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_employee_photo(client, admin_token, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.employees.cloudinary.uploader.upload",
        lambda *args, **kwargs: {
            "secure_url": "https://res.cloudinary.com/test/image/upload/avatar.png",
        },
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    email = f"photo_{uuid.uuid4().hex[:6]}@example.com"
    created = await client.post("/api/v1/employees", json={
        "email": email, "password": "testpass123",
        "first_name": "Photo", "last_name": "Test",
        "date_of_joining": "2026-09-15",
    }, headers=headers)
    employee_id = created.json()["id"]

    bad = await client.post(
        f"/api/v1/employees/{employee_id}/photo",
        files={"file": ("note.txt", b"not an image", "text/plain")},
        headers=headers,
    )
    assert bad.status_code == 400

    # 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    good = await client.post(
        f"/api/v1/employees/{employee_id}/photo",
        files={"file": ("avatar.png", png, "image/png")},
        headers=headers,
    )
    assert good.status_code == 200
    assert good.json()["photo_url"].startswith("https://")

    assert (await client.delete(f"/api/v1/employees/{employee_id}", headers=headers)).status_code == 204


async def _hr_headers(client, admin_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    email = f"hrdel_{uuid.uuid4().hex[:6]}@example.com"
    created = await client.post("/api/v1/users", json={
        "email": email, "password": "testpass123", "role": "hr",
        "first_name": "HR", "last_name": "Del",
    }, headers=h_admin)
    assert created.status_code == 200
    login = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "testpass123"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, email


async def _employee_profile_id(client, admin_token, prefix="victim"):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    created = await client.post("/api/v1/employees", json={
        "email": email, "password": "testpass123",
        "first_name": "Victim", "last_name": "User",
        "date_of_joining": "2026-09-15",
    }, headers=h_admin)
    assert created.status_code == 200
    return created.json()["id"]


async def _profile_id_for_email(client, admin_token, email):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    listed = await client.get("/api/v1/employees", headers=h_admin)
    return next(e["id"] for e in listed.json() if e["email"] == email)


@pytest.mark.asyncio
async def test_hr_delete_rules(client, admin_token, employee_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_emp = {"Authorization": f"Bearer {employee_token}"}
    h_hr, hr_email = await _hr_headers(client, admin_token)

    # HR can delete an employee profile
    victim_id = await _employee_profile_id(client, admin_token)
    assert (await client.delete(f"/api/v1/employees/{victim_id}", headers=h_hr)).status_code == 204

    # HR cannot delete its own (HR-role) profile
    own_profile = await _profile_id_for_email(client, admin_token, hr_email)
    assert (await client.delete(f"/api/v1/employees/{own_profile}", headers=h_hr)).status_code == 403

    # HR cannot delete another HR's profile; admin can delete anyone
    _h_hr2, hr2_email = await _hr_headers(client, admin_token)
    hr2_profile = await _profile_id_for_email(client, admin_token, hr2_email)
    assert (await client.delete(f"/api/v1/employees/{hr2_profile}", headers=h_hr)).status_code == 403
    assert (await client.delete(f"/api/v1/employees/{hr2_profile}", headers=h_admin)).status_code == 204

    # HR cannot delete an admin-role profile either
    adm_email = f"admprof_{uuid.uuid4().hex[:6]}@example.com"
    adm = await client.post("/api/v1/users", json={
        "email": adm_email, "password": "testpass123",
        "role": "admin", "first_name": "Adm", "last_name": "Prof",
    }, headers=h_admin)
    assert adm.status_code == 200
    adm_profile = await _profile_id_for_email(client, admin_token, adm_email)
    assert (await client.delete(f"/api/v1/employees/{adm_profile}", headers=h_hr)).status_code == 403
    assert (await client.delete(f"/api/v1/employees/{adm_profile}", headers=h_admin)).status_code == 204

    # employee role cannot delete anyone
    victim2 = await _employee_profile_id(client, admin_token, prefix="victim2")
    assert (await client.delete(f"/api/v1/employees/{victim2}", headers=h_emp)).status_code == 403
    assert (await client.delete(f"/api/v1/employees/{victim2}", headers=h_admin)).status_code == 204


@pytest.mark.asyncio
async def test_hr_edit_rules(client, admin_token):
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_hr, _ = await _hr_headers(client, admin_token)

    victim = await _employee_profile_id(client, admin_token, prefix="editemp")
    assert (await client.patch(
        f"/api/v1/employees/{victim}", json={"phone": "9999999999"}, headers=h_hr
    )).status_code == 200

    # HR cannot edit an admin-role profile
    adm_email = f"admupd_{uuid.uuid4().hex[:6]}@example.com"
    await client.post("/api/v1/users", json={
        "email": adm_email, "password": "testpass123",
        "role": "admin", "first_name": "Adm", "last_name": "Upd",
    }, headers=h_admin)
    adm_profile = await _profile_id_for_email(client, admin_token, adm_email)
    assert (await client.patch(
        f"/api/v1/employees/{adm_profile}", json={"phone": "9999999998"}, headers=h_hr
    )).status_code == 403
    assert (await client.patch(
        f"/api/v1/employees/{adm_profile}", json={"phone": "9999999998"}, headers=h_admin
    )).status_code == 200


@pytest.mark.asyncio
async def test_employee_rejects_bad_phone_and_blank_names(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    base = {
        "email": f"bad_{uuid.uuid4().hex[:6]}@example.com", "password": "testpass123",
        "first_name": "Bad", "last_name": "Data",
        "date_of_joining": "2026-09-15",
    }
    assert (await client.post("/api/v1/employees", json={**base, "phone": "111"}, headers=h)).status_code == 422
    assert (await client.post("/api/v1/employees", json={**base, "first_name": "   "}, headers=h)).status_code == 422
