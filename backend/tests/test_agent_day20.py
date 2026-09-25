import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.agent.evaluation import load_intent_cases, run_intent_evaluation
from app.core.security import hash_password
from app.db.session import async_session
from app.models.agent_conversation import AgentConversation
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.models.role import RoleEnum
from app.models.user import User
from app.rag.generation import GroundedAnswer
from app.rag.retrieval import RetrievedChunk

PASSWORD = "ScenarioPass!42"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_actor(
    role: RoleEnum, label: str
) -> tuple[uuid.UUID, uuid.UUID, str, str]:
    email = f"{label}_{uuid.uuid4().hex}@test.local"
    async with async_session() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(PASSWORD),
            role=role,
        )
        db.add(user)
        await db.flush()
        employee = Employee(
            id=uuid.uuid4(),
            user_id=user.id,
            first_name=label.title(),
            last_name="Scenario",
            date_of_joining=datetime.now(UTC).date(),
        )
        db.add(employee)
        await db.commit()
        return user.id, employee.id, email, PASSWORD


async def login(client, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def cleanup_users(*user_ids: uuid.UUID) -> None:
    async with async_session() as db:
        employee_ids = list(
            (
                await db.scalars(
                    select(Employee.id).where(Employee.user_id.in_(user_ids))
                )
            ).all()
        )
        await db.execute(
            delete(AgentConversation).where(AgentConversation.user_id.in_(user_ids))
        )
        if employee_ids:
            await db.execute(
                delete(LeaveBalance).where(LeaveBalance.employee_id.in_(employee_ids))
            )
            await db.execute(delete(Employee).where(Employee.id.in_(employee_ids)))
        await db.execute(delete(User).where(User.id.in_(user_ids)))
        await db.commit()


def test_day20_intent_evaluation_meets_target():
    report = run_intent_evaluation(load_intent_cases())
    assert report.total == 10
    assert report.passed >= 8
    assert report.target_met is True


@pytest.mark.asyncio
async def test_scenario_1_policy_question_returns_grounded_citation(
    client, monkeypatch
):
    user_id, _, email, password = await create_actor(
        RoleEnum.EMPLOYEE, "policy_employee"
    )
    token = await login(client, email, password)
    document_id = uuid.uuid4()
    chunk = RetrievedChunk(
        document_id=document_id,
        title="Work From Home Policy",
        category="policy",
        chunk_index=0,
        page_number=2,
        content="Employees may work from home two days per week.",
        cosine_distance=0.08,
    )

    async def fake_retrieve(db, question):
        assert question == "What's the work-from-home policy?"
        return [chunk]

    async def fake_generate(question, chunks, **kwargs):
        return GroundedAnswer(
            answer="Employees may work from home two days per week.",
            source_numbers=[1],
        )

    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.retrieve_policy_chunks", fake_retrieve
    )
    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.generate_grounded_answer", fake_generate
    )

    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "What's the work-from-home policy?"},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "rag"
    assert "two days" in body["answer"].lower()
    assert body["sources"][0]["document_id"] == str(document_id)
    assert body["sources"][0]["page_number"] == 2
    await cleanup_users(user_id)


@pytest.mark.asyncio
async def test_scenario_2_leave_query_returns_only_authenticated_balance(client):
    user_id, employee_id, email, password = await create_actor(
        RoleEnum.EMPLOYEE, "leave_employee"
    )
    other_user_id, other_employee_id, _, _ = await create_actor(
        RoleEnum.EMPLOYEE, "other_leave_employee"
    )
    leave_type_id = uuid.uuid4()
    async with async_session() as db:
        db.add(
            LeaveType(
                id=leave_type_id,
                name=f"Scenario Leave {uuid.uuid4().hex}",
                default_annual_days=12,
            )
        )
        await db.flush()
        db.add_all(
            [
                LeaveBalance(
                    employee_id=employee_id,
                    leave_type_id=leave_type_id,
                    year=datetime.now(UTC).year,
                    total_days=12,
                    used_days=4,
                ),
                LeaveBalance(
                    employee_id=other_employee_id,
                    leave_type_id=leave_type_id,
                    year=datetime.now(UTC).year,
                    total_days=99,
                    used_days=0,
                ),
            ]
        )
        await db.commit()

    token = await login(client, email, password)
    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "How many leaves do I have left?"},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "database"
    assert "8 of 12 remaining" in body["answer"]
    assert "99" not in body["answer"]

    await cleanup_users(user_id, other_user_id)
    async with async_session() as db:
        await db.execute(delete(LeaveType).where(LeaveType.id == leave_type_id))
        await db.commit()


@pytest.mark.asyncio
async def test_scenario_3_hr_creates_employee_through_follow_up_flow(client):
    hr_user_id, _, email, password = await create_actor(RoleEnum.HR, "scenario_hr")
    token = await login(client, email, password)
    new_email = f"priya_day20_{uuid.uuid4().hex}@test.local"

    first = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Add employee Priya Singh"},
        headers=auth(token),
    )
    assert first.status_code == 200, first.text
    assert first.json()["intent"] == "action"
    assert "email" in first.json()["answer"].lower()
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/agent/chat",
        json={"message": new_email, "conversation_id": conversation_id},
        headers=auth(token),
    )
    assert "joining date" in second.json()["answer"].lower()

    third = await client.post(
        "/api/v1/agent/chat",
        json={"message": "2026-10-01", "conversation_id": conversation_id},
        headers=auth(token),
    )
    assert "temporary password" in third.json()["answer"].lower()

    completed = await client.post(
        "/api/v1/agent/chat",
        json={"message": "TemporaryEmployee!42", "conversation_id": conversation_id},
        headers=auth(token),
    )
    assert completed.status_code == 200, completed.text
    assert "created employee priya singh" in completed.json()["answer"].lower()

    async with async_session() as db:
        created_user = await db.scalar(select(User).where(User.email == new_email))
        assert created_user is not None
        assert created_user.role == RoleEnum.EMPLOYEE
        created_employee = await db.scalar(
            select(Employee).where(Employee.user_id == created_user.id)
        )
        assert created_employee is not None
        assert created_employee.first_name == "Priya"
        assert created_employee.last_name == "Singh"
        created_user_id = created_user.id

    await cleanup_users(hr_user_id, created_user_id)


@pytest.mark.asyncio
async def test_scenario_4_employee_cannot_delete_employee(client):
    actor_user_id, _, email, password = await create_actor(
        RoleEnum.EMPLOYEE, "unauthorized_actor"
    )
    target_user_id, target_employee_id, _, _ = await create_actor(
        RoleEnum.EMPLOYEE, "protected_target"
    )
    token = await login(client, email, password)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": f"Delete employee {target_employee_id}"},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "action"
    assert "does not have permission" in body["answer"].lower()
    assert "confirm" not in body["answer"].lower()

    async with async_session() as db:
        assert await db.get(Employee, target_employee_id) is not None
        assert (await db.get(User, target_user_id)).is_active is True
        conversation = await db.get(
            AgentConversation, uuid.UUID(body["conversation_id"])
        )
        assert conversation.pending_action is None

    await cleanup_users(actor_user_id, target_user_id)
