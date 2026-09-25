import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from app.agent.memory import RECENT_MESSAGE_LIMIT, load_conversation_memory
from app.agent.nodes.rag_agent import run_policy_rag
from app.agent.state import AgentState
from app.db.session import async_session
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.employee import Employee
from app.models.leave import LeaveBalance
from app.models.role import RoleEnum
from app.models.user import User
from app.rag.generation import GroundedAnswer
from app.rag.retrieval import RetrievedChunk


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def remove_conversation(conversation_id: uuid.UUID) -> None:
    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(AgentConversation.id == conversation_id)
        )
        await db.commit()


@pytest.mark.asyncio
async def test_conversation_memory_persists_recent_messages_and_summary(
    client, employee_token
):
    conversation_id = None
    for number in range(6):
        payload = {"message": f"Hello message {number}"}
        if conversation_id:
            payload["conversation_id"] = str(conversation_id)
        response = await client.post(
            "/api/v1/agent/chat", json=payload, headers=auth(employee_token)
        )
        assert response.status_code == 200, response.text
        conversation_id = uuid.UUID(response.json()["conversation_id"])

    async with async_session() as db:
        conversation = await db.get(AgentConversation, conversation_id)
        assert conversation is not None
        assert conversation.summary
        history, summary, _ = await load_conversation_memory(
            db, conversation.user_id, conversation_id
        )
        message_count = await db.scalar(
            select(func.count(AgentMessage.id)).where(
                AgentMessage.conversation_id == conversation_id
            )
        )
        assert message_count == 12
        assert len(history) == RECENT_MESSAGE_LIMIT
        assert "Hello message 0" in summary

    await remove_conversation(conversation_id)


@pytest.mark.asyncio
async def test_conversation_cannot_be_opened_by_another_user(
    client, employee_token, admin_token
):
    created = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello from the employee"},
        headers=auth(employee_token),
    )
    assert created.status_code == 200
    conversation_id = uuid.UUID(created.json()["conversation_id"])

    forbidden = await client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Show me this conversation",
            "conversation_id": str(conversation_id),
        },
        headers=auth(admin_token),
    )
    assert forbidden.status_code == 404
    assert forbidden.json()["detail"] == "Conversation not found."

    await remove_conversation(conversation_id)


@pytest.mark.asyncio
async def test_delete_waits_for_confirmation_before_database_write(client, admin_token):
    async with async_session() as db:
        target_user = User(
            id=uuid.uuid4(),
            email=f"confirm_target_{uuid.uuid4().hex}@test.local",
            hashed_password="unused",
            role=RoleEnum.EMPLOYEE,
        )
        db.add(target_user)
        await db.flush()
        target = Employee(
            id=uuid.uuid4(),
            user_id=target_user.id,
            first_name="Confirmation",
            last_name="Target",
            date_of_joining=datetime.now(UTC).date(),
        )
        db.add(target)
        await db.commit()
        target_id = target.id
        target_user_id = target_user.id

    requested = await client.post(
        "/api/v1/agent/chat",
        json={"message": f"Delete employee {target_id}"},
        headers=auth(admin_token),
    )
    assert requested.status_code == 200, requested.text
    assert "confirm" in requested.json()["answer"].lower()
    conversation_id = uuid.UUID(requested.json()["conversation_id"])

    async with async_session() as db:
        assert await db.get(Employee, target_id) is not None
        assert (await db.get(User, target_user_id)).is_active is True

    confirmed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "confirm", "conversation_id": str(conversation_id)},
        headers=auth(admin_token),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert "deleted successfully" in confirmed.json()["answer"].lower()

    async with async_session() as db:
        assert await db.get(Employee, target_id) is None
        assert (await db.get(User, target_user_id)).is_active is False
        await db.execute(
            delete(AgentConversation).where(AgentConversation.id == conversation_id)
        )
        await db.execute(delete(User).where(User.id == target_user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_create_employee_collects_missing_fields_across_messages(
    client, admin_token
):
    email = f"priya_{uuid.uuid4().hex}@test.local"
    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Add employee Priya Singh"},
        headers=auth(admin_token),
    )
    assert first.status_code == 200, first.text
    assert "email" in first.json()["answer"].lower()
    conversation_id = uuid.UUID(first.json()["conversation_id"])

    second = await client.post(
        "/api/v1/agent/chat",
        json={"message": email, "conversation_id": str(conversation_id)},
        headers=auth(admin_token),
    )
    assert "joining date" in second.json()["answer"].lower()

    third = await client.post(
        "/api/v1/agent/chat",
        json={"message": "2026-10-01", "conversation_id": str(conversation_id)},
        headers=auth(admin_token),
    )
    assert "temporary password" in third.json()["answer"].lower()

    password = "TemporaryPass!42"
    completed = await client.post(
        "/api/v1/agent/chat",
        json={"message": password, "conversation_id": str(conversation_id)},
        headers=auth(admin_token),
    )
    assert completed.status_code == 200, completed.text
    assert "created employee priya singh" in completed.json()["answer"].lower()

    async with async_session() as db:
        created_user = await db.scalar(select(User).where(User.email == email))
        assert created_user is not None
        employee = await db.scalar(
            select(Employee).where(Employee.user_id == created_user.id)
        )
        assert employee is not None
        stored_messages = list(
            (
                await db.scalars(
                    select(AgentMessage).where(
                        AgentMessage.conversation_id == conversation_id
                    )
                )
            ).all()
        )
        assert password not in {message.content for message in stored_messages}
        assert "[Sensitive value provided]" in {
            message.content for message in stored_messages
        }

        await db.execute(
            delete(AgentConversation).where(AgentConversation.id == conversation_id)
        )
        await db.execute(
            delete(LeaveBalance).where(LeaveBalance.employee_id == employee.id)
        )
        await db.execute(delete(Employee).where(Employee.id == employee.id))
        await db.execute(delete(User).where(User.id == created_user.id))
        await db.commit()


@pytest.mark.asyncio
async def test_bulk_delete_requires_confirmation_but_remains_disabled(
    client, admin_token
):
    requested = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Delete all test employee records"},
        headers=auth(admin_token),
    )
    assert requested.status_code == 200, requested.text
    assert "bulk destructive" in requested.json()["answer"].lower()
    conversation_id = uuid.UUID(requested.json()["conversation_id"])

    confirmed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "confirm", "conversation_id": str(conversation_id)},
        headers=auth(admin_token),
    )
    assert confirmed.status_code == 200
    assert "not enabled" in confirmed.json()["answer"].lower()
    assert "no records were changed" in confirmed.json()["answer"].lower()

    await remove_conversation(conversation_id)


@pytest.mark.asyncio
async def test_rag_sends_recent_history_and_summary_to_gemini(monkeypatch):
    chunk = RetrievedChunk(
        document_id=uuid.uuid4(),
        title="WFH Policy",
        category="policy",
        chunk_index=0,
        page_number=1,
        content="Employees may work remotely two days each week.",
        cosine_distance=0.1,
    )

    async def fake_retrieve(db, question):
        assert question == "What about during probation?"
        return [chunk]

    async def fake_generate(question, chunks, *, conversation_context):
        assert (
            "Earlier summary: User previously asked about WFH." in conversation_context
        )
        assert "Assistant: Employees may work remotely." in conversation_context
        return GroundedAnswer(
            answer="The policy applies during probation.", source_numbers=[1]
        )

    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.retrieve_policy_chunks", fake_retrieve
    )
    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.generate_grounded_answer", fake_generate
    )
    state: AgentState = {
        "user_id": uuid.uuid4(),
        "role": RoleEnum.EMPLOYEE,
        "message": "What about during probation?",
        "conversation_summary": "User previously asked about WFH.",
        "history": [
            {"role": "user", "content": "What is the WFH policy?"},
            {"role": "assistant", "content": "Employees may work remotely."},
        ],
    }

    result = await run_policy_rag(state, object())
    assert result["tool_result"]["status"] == "success"
