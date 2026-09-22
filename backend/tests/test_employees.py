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
async def test_upload_employee_photo(client, admin_token):
    import cloudinary.uploader

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

    public_id = good.json()["photo_url"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cloudinary.uploader.destroy(f"hrms/employees/{public_id}", resource_type="image")
    assert (await client.delete(f"/api/v1/employees/{employee_id}", headers=headers)).status_code == 204