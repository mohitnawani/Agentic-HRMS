import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.agent.nodes.action_agent import select_action_tool
from app.db.session import async_session
from app.models.agent_conversation import AgentConversation
from app.models.announcement import Announcement


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("add policies", "upload_policy"),
        ("Add Policies", "upload_policy"),
        ("upload policy document", "upload_policy"),
        ("delete policy", "delete_policy"),
        ("edit user", "update_employee"),
        ("update employee", "update_employee"),
        ("delete user", "delete_employee"),
        ("Apply for leave", "apply_leave"),
        ("cancel leave", "cancel_leave"),
        ("check in", "check_in"),
        ("check-out", "check_out"),
    ],
)
def test_action_tool_accepts_common_hr_phrases(message, expected):
    assert select_action_tool(message) == expected


@pytest.mark.asyncio
async def test_employee_can_start_leave_application(client, employee_token):
    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Apply for leave"},
        headers=auth(employee_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "action"
    assert "leave type" in body["answer"].lower()

    repeated = await client.post(
        "/api/v1/agent/chat",
        json={
            "message": "I want to apply for leave",
            "conversation_id": body["conversation_id"],
        },
        headers=auth(employee_token),
    )
    assert "leave type" in repeated.json()["answer"].lower()

    pending = await client.get(
        f"/api/v1/agent/conversations/{body['conversation_id']}",
        headers=auth(employee_token),
    )
    assert pending.json()["pending_interaction"] == {
        "tool": "apply_leave",
        "stage": "slots",
        "missing_field": "leave_type_id",
    }

    cancelled = await client.post(
        "/api/v1/agent/chat",
        json={"message": "cancel", "conversation_id": body["conversation_id"]},
        headers=auth(employee_token),
    )
    assert "cancelled" in cancelled.json()["answer"].lower()

    cleared = await client.get(
        f"/api/v1/agent/conversations/{body['conversation_id']}",
        headers=auth(employee_token),
    )
    assert cleared.json()["pending_interaction"] is None

    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(body["conversation_id"])
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_failed_leave_confirmation_does_not_trap_next_application(
    client, employee_token
):
    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Apply for leave"},
        headers=auth(employee_token),
    )
    conversation_id = first.json()["conversation_id"]
    day = datetime.now(UTC).date().isoformat()

    review = await client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Review leave request",
            "conversation_id": conversation_id,
            "parameters": {
                "leave_type_id": str(uuid.uuid4()),
                "start_date": day,
                "end_date": day,
                "reason": "Personal appointment",
            },
        },
        headers=auth(employee_token),
    )
    assert "confirm" in review.json()["answer"].lower()

    failed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "confirm", "conversation_id": conversation_id},
        headers=auth(employee_token),
    )
    assert "leave type not found" in failed.json()["answer"].lower()

    restored = await client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=auth(employee_token),
    )
    assert restored.json()["pending_interaction"] is None

    restarted = await client.post(
        "/api/v1/agent/chat",
        json={"message": "I want to apply for leave", "conversation_id": conversation_id},
        headers=auth(employee_token),
    )
    assert "leave type" in restarted.json()["answer"].lower()

    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(conversation_id)
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_agent_creates_announcement_after_confirmation(client, admin_token):
    title = f"Office Update {uuid.uuid4().hex}"
    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Create announcement"},
        headers=auth(admin_token),
    )
    conversation_id = first.json()["conversation_id"]
    assert "title" in first.json()["answer"].lower()

    second = await client.post(
        "/api/v1/agent/chat",
        json={"message": title, "conversation_id": conversation_id},
        headers=auth(admin_token),
    )
    assert "announcement say" in second.json()["answer"].lower()

    third = await client.post(
        "/api/v1/agent/chat",
        json={
            "message": "The office will close at 4 PM on Friday.",
            "conversation_id": conversation_id,
        },
        headers=auth(admin_token),
    )
    assert "confirm" in third.json()["answer"].lower()

    completed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "confirm", "conversation_id": conversation_id},
        headers=auth(admin_token),
    )
    assert "published announcement" in completed.json()["answer"].lower()

    async with async_session() as db:
        announcement = await db.scalar(
            select(Announcement).where(Announcement.title == title)
        )
        assert announcement is not None
        await db.delete(announcement)
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(conversation_id)
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_agent_collects_policy_metadata_before_file_upload(client, admin_token):
    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "add policies"},
        headers=auth(admin_token),
    )
    conversation_id = first.json()["conversation_id"]
    assert "title" in first.json()["answer"].lower()

    second = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Remote Work Policy", "conversation_id": conversation_id},
        headers=auth(admin_token),
    )
    assert "category" in second.json()["answer"].lower()

    third = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Workplace", "conversation_id": conversation_id},
        headers=auth(admin_token),
    )
    assert "pdf" in third.json()["answer"].lower()

    restored = await client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=auth(admin_token),
    )
    pending = restored.json()["pending_interaction"]
    assert pending == {
        "tool": "upload_policy",
        "stage": "slots",
        "missing_field": "policy_file",
        "parameters": {
            "title": "Remote Work Policy",
            "category": "Workplace",
        },
    }

    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(conversation_id)
            )
        )
        await db.commit()
