import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from app.db.session import async_session
from app.models.agent_conversation import AgentConversation
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        event = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


def event_data(events: list[tuple[str, dict]], event_name: str) -> dict:
    return next(data for event, data in events if event == event_name)


async def delete_conversation(conversation_id: str) -> None:
    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(conversation_id)
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_conversation_history_restores_only_for_owner(
    client, employee_token, admin_token
):
    created = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello assistant"},
        headers=auth(employee_token),
    )
    conversation_id = created.json()["conversation_id"]

    restored = await client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=auth(employee_token),
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert [message["role"] for message in body["messages"]] == [
        "user",
        "assistant",
    ]
    assert body["messages"][0]["content"] == "Hello assistant"
    assert body["pending_interaction"] is None

    foreign = await client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=auth(admin_token),
    )
    assert foreign.status_code == 404
    await delete_conversation(conversation_id)


@pytest.mark.asyncio
async def test_slot_follow_up_exposes_structured_ui_metadata(client, admin_token):
    response = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": "Add employee Priya Singh"},
        headers=auth(admin_token),
    )
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    conversation_id = event_data(events, "meta")["conversation_id"]
    tool = event_data(events, "tool")
    assert tool["status"] == "needs_input"
    assert tool["tool"] == "create_employee"
    assert tool["data"] == {"stage": "slots", "missing_field": "email"}

    restored = await client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=auth(admin_token),
    )
    assert restored.json()["pending_interaction"] == {
        "tool": "create_employee",
        "stage": "slots",
        "missing_field": "email",
    }
    await delete_conversation(conversation_id)


@pytest.mark.asyncio
async def test_confirmation_buttons_can_cancel_without_database_write(
    client, admin_token
):
    async with async_session() as db:
        target_user = User(
            id=uuid.uuid4(),
            email=f"day22_target_{uuid.uuid4().hex}@test.local",
            hashed_password="unused",
            role=RoleEnum.EMPLOYEE,
        )
        db.add(target_user)
        await db.flush()
        target = Employee(
            id=uuid.uuid4(),
            user_id=target_user.id,
            first_name="Day22",
            last_name="Target",
            date_of_joining=datetime.now(UTC).date(),
        )
        db.add(target)
        await db.commit()
        target_id = target.id
        target_user_id = target_user.id

    requested = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": f"Delete employee {target_id}"},
        headers=auth(admin_token),
    )
    events = parse_sse(requested.text)
    conversation_id = event_data(events, "meta")["conversation_id"]
    confirmation = event_data(events, "tool")
    assert confirmation["status"] == "confirmation_required"
    assert confirmation["data"] == {"stage": "confirmation"}

    cancelled = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": "cancel", "conversation_id": conversation_id},
        headers=auth(admin_token),
    )
    cancel_tool = event_data(parse_sse(cancelled.text), "tool")
    assert cancel_tool["status"] == "cancelled"

    async with async_session() as db:
        assert await db.get(Employee, target_id) is not None
        assert (await db.get(User, target_user_id)).is_active is True
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(conversation_id)
            )
        )
        await db.execute(delete(Employee).where(Employee.id == target_id))
        await db.execute(delete(User).where(User.id == target_user_id))
        await db.commit()
