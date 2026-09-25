import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.agent_conversation import AgentConversation
from app.models.announcement import Announcement


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
        json={"message": "Upload policy"},
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
