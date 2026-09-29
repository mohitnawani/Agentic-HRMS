"""Dashboard and headcount queries: routing, selection, and permission gating."""

import uuid
from datetime import UTC, datetime

import pytest

from app.agent.nodes.database_agent import run_database_query, select_database_tool
from app.agent.state import AgentState
from app.agent.supervisor import classify_intent, route_from_supervisor, supervisor_node
from app.agent.tools.read_tools import get_org_stats
from app.core.security import hash_password
from app.db.session import async_session
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


def _state(user_id: uuid.UUID, role: RoleEnum, message: str) -> AgentState:
    return {"user_id": user_id, "role": role, "message": message}  # type: ignore[typeddict-item]


async def _actor(role: RoleEnum, label: str) -> User:
    async with async_session() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"{label}_{uuid.uuid4().hex}@test.local",
            hashed_password=hash_password("testpass123"),
            role=role,
        )
        session.add(user)
        await session.flush()
        session.add(
            Employee(
                id=uuid.uuid4(),
                user_id=user.id,
                first_name=label.title(),
                last_name="Tester",
                date_of_joining=datetime.now(UTC).date(),
            )
        )
        await session.commit()
        return user


def test_dashboard_and_count_queries_classify_as_database() -> None:
    for message in (
        "show me dashboard",
        "open the dashboard",
        "how many departments are there",
        "how many employees",
        "how many designations and departments",
        "organization overview",
    ):
        assert classify_intent(message) == "database", message


def test_action_and_rag_routing_untouched() -> None:
    assert classify_intent("create announcement") == "action"
    assert classify_intent("what is the leave policy") == "rag"
    node = supervisor_node(
        _state(uuid.uuid4(), RoleEnum.ADMIN, "show me dashboard")
    )
    assert node["intent"] == "database"
    assert route_from_supervisor({**node, "intent": node["intent"]}) == "database_agent"


def test_selector_routes_counts_and_dashboard() -> None:
    assert select_database_tool("show me dashboard") == "get_org_stats"
    assert select_database_tool("how many designations and departments") == "get_org_stats"
    assert select_database_tool("organization stats") == "get_org_stats"
    assert select_database_tool("how many employees") == "list_employees"
    assert select_database_tool("how many departments are there") == "list_departments"
    assert select_database_tool("list all employees in Engineering") == "list_employees"
    assert select_database_tool("list users") == "list_users"
    assert select_database_tool("show all employee attendance") == "list_attendance_records"
    assert select_database_tool("show my attendance") == "get_attendance_summary"


@pytest.mark.asyncio
async def test_hr_attendance_query_uses_organization_records_not_own_summary() -> None:
    hr = await _actor(RoleEnum.HR, "attendancehr")
    async with async_session() as session:
        result = await run_database_query(
            _state(hr.id, RoleEnum.HR, "show all employee attendance"), session
        )
    assert result["status"] == "success"
    assert result["tool"] == "list_attendance_records"
    assert "attendance_records" in result["data"]


@pytest.mark.asyncio
async def test_org_stats_admin_sees_all_metrics() -> None:
    admin = await _actor(RoleEnum.ADMIN, "orgstat")
    async with async_session() as session:
        stats = await get_org_stats(
            _state(admin.id, RoleEnum.ADMIN, "show me dashboard"), session
        )
    assert set(stats) == {
        "total_employees",
        "departments",
        "designations",
        "user_accounts",
        "holidays_this_year",
        "active_announcements",
        "pending_leave_requests",
        "policy_documents",
    }
    assert all(isinstance(value, int) and value >= 0 for value in stats.values())
    assert stats["total_employees"] >= 1


@pytest.mark.asyncio
async def test_org_stats_employee_excludes_restricted_metrics() -> None:
    employee = await _actor(RoleEnum.EMPLOYEE, "orgstatemp")
    async with async_session() as session:
        stats = await get_org_stats(
            _state(employee.id, RoleEnum.EMPLOYEE, "show me dashboard"), session
        )
    assert "total_employees" not in stats
    assert "user_accounts" not in stats
    assert "pending_leave_requests" not in stats
    assert stats["departments"] >= 0
    assert stats["holidays_this_year"] >= 0


@pytest.mark.asyncio
async def test_run_database_query_reports_overview() -> None:
    admin = await _actor(RoleEnum.ADMIN, "orgstatrun")
    async with async_session() as session:
        result = await run_database_query(
            _state(admin.id, RoleEnum.ADMIN, "show me dashboard"), session
        )
    assert result["status"] == "success"
    assert result["tool"] == "get_org_stats"
    assert "Organization overview" in result["message"]
    assert "employees" in result["message"]
