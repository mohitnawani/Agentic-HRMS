import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.rag_agent import run_policy_rag
from app.agent.state import AgentState
from app.agent.tools.read_tools import (
    ReadToolAccessDenied,
    get_attendance_summary,
    get_employee_details,
    get_leave_balance,
    list_employees,
)
from app.db.session import async_session
from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.models.role import RoleEnum
from app.models.user import User
from app.rag.generation import GroundedAnswer
from app.rag.retrieval import RetrievedChunk


async def create_actor(
    db: AsyncSession, role: RoleEnum, label: str
) -> tuple[User, Employee]:
    user = User(
        id=uuid.uuid4(),
        email=f"{label}_{uuid.uuid4().hex}@test.local",
        hashed_password="unused",
        role=role,
    )
    db.add(user)
    await db.flush()
    employee = Employee(
        id=uuid.uuid4(),
        user_id=user.id,
        first_name=label.title(),
        last_name="Tester",
        date_of_joining=datetime.now(UTC).date(),
    )
    db.add(employee)
    await db.flush()
    return user, employee


def state_for(user: User, message: str = "test") -> AgentState:
    return {"user_id": user.id, "role": user.role, "message": message}


@pytest.mark.asyncio
async def test_self_service_tools_are_scoped_to_authenticated_employee():
    async with async_session() as db:
        actor, employee = await create_actor(db, RoleEnum.EMPLOYEE, "scoped")
        other, other_employee = await create_actor(db, RoleEnum.EMPLOYEE, "other")
        leave_type = LeaveType(
            id=uuid.uuid4(),
            name=f"Scoped Leave {uuid.uuid4().hex}",
            default_annual_days=12,
        )
        db.add(leave_type)
        await db.flush()
        db.add_all(
            [
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=leave_type.id,
                    year=datetime.now(UTC).year,
                    total_days=12,
                    used_days=3,
                ),
                LeaveBalance(
                    employee_id=other_employee.id,
                    leave_type_id=leave_type.id,
                    year=datetime.now(UTC).year,
                    total_days=99,
                    used_days=0,
                ),
                Attendance(
                    employee_id=employee.id,
                    date=datetime.now(UTC).date(),
                    status=AttendanceStatus.PRESENT,
                ),
            ]
        )
        await db.flush()

        balance = await get_leave_balance(state_for(actor), db)
        attendance = await get_attendance_summary(state_for(actor), db)

        assert balance["employee_id"] == str(employee.id)
        assert balance["balances"][0]["remaining_days"] == 9
        assert all(item["total_days"] != 99 for item in balance["balances"])
        assert attendance["employee_id"] == str(employee.id)
        assert attendance["present"] == 1
        assert other.id != actor.id
        await db.rollback()


@pytest.mark.asyncio
async def test_employee_cannot_list_or_read_another_employee():
    async with async_session() as db:
        actor, _ = await create_actor(db, RoleEnum.EMPLOYEE, "restricted")
        _, other_employee = await create_actor(db, RoleEnum.EMPLOYEE, "target")

        with pytest.raises(ReadToolAccessDenied):
            await list_employees(state_for(actor), db)
        with pytest.raises(ReadToolAccessDenied):
            await get_employee_details(
                state_for(actor), db, employee_id=other_employee.id
            )
        await db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [RoleEnum.ADMIN, RoleEnum.HR])
async def test_admin_and_hr_can_list_employees(role):
    async with async_session() as db:
        actor, actor_employee = await create_actor(db, role, role.value)
        employees = await list_employees(state_for(actor), db)
        assert str(actor_employee.id) in {item["employee_id"] for item in employees}
        await db.rollback()


@pytest.mark.asyncio
async def test_rag_node_wraps_grounded_pipeline_with_citations(monkeypatch):
    document_id = uuid.uuid4()
    chunk = RetrievedChunk(
        document_id=document_id,
        title="WFH Policy",
        category="policy",
        chunk_index=2,
        page_number=3,
        content="Employees may work from home two days per week.",
        cosine_distance=0.12,
    )

    async def fake_retrieve(db, question):
        assert question == "What is the WFH policy?"
        return [chunk]

    async def fake_generate(question, chunks):
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
    state: AgentState = {
        "user_id": uuid.uuid4(),
        "role": RoleEnum.EMPLOYEE,
        "message": "What is the WFH policy?",
    }

    result = await run_policy_rag(state, object())

    assert result["tool_result"]["status"] == "success"
    assert result["tool_result"]["data"]["sources"][0]["document_id"] == str(
        document_id
    )
    assert result["retrieved_context"][0]["page_number"] == 3


@pytest.mark.asyncio
async def test_agent_endpoint_requires_authentication(client):
    response = await client.post(
        "/api/v1/agent/chat", json={"message": "How many leaves do I have?"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_endpoint_routes_authenticated_database_query(
    client, employee_token
):
    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "How many leaves do I have left?"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["intent"] == "database"
    assert "leave balance" in response.json()["answer"].lower()
