import uuid

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import agent_graph
from app.agent.nodes import database_agent as database_module
from app.agent.nodes import rag_agent as rag_module
from app.models.role import RoleEnum


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message,expected_intent,expected_node",
    [
        ("What is the work-from-home policy?", "rag", "rag_agent"),
        ("How many leaves do I have remaining?", "database", "database_agent"),
        ("Show all employees in Engineering", "database", "database_agent"),
        ("Create a new employee", "action", "action_agent"),
        ("Approve Rahul's leave request", "action", "action_agent"),
        ("Hello, what can you help me with?", "general", None),
    ],
)
async def test_graph_routes_requests(
    message, expected_intent, expected_node, monkeypatch
):
    async def fake_database(state, db):
        return {
            "agent": "database",
            "status": "success",
            "tool": "test_tool",
            "message": "Database result",
        }

    async def fake_rag(state, db):
        return {
            "tool_result": {
                "agent": "rag",
                "status": "success",
                "tool": "policy_rag",
                "message": "Grounded policy result",
                "data": {"sources": []},
            },
            "retrieved_context": [],
        }

    monkeypatch.setattr(database_module, "run_database_query", fake_database)
    monkeypatch.setattr(rag_module, "run_policy_rag", fake_rag)
    user_id = uuid.uuid4()
    result = await agent_graph.ainvoke(
        {
            "user_id": user_id,
            "role": RoleEnum.EMPLOYEE,
            "message": message,
            "history": [],
        },
        context={"db": object()},
    )

    assert result["user_id"] == user_id
    assert result["role"] == RoleEnum.EMPLOYEE
    assert result["intent"] == expected_intent
    assert result["route_trace"][0] == "supervisor"
    assert result["route_trace"][-1] == "response_generator"
    assert bool(result.get("final_answer"))
    if expected_node:
        assert expected_node in result["route_trace"]
        expected_status = "stub" if expected_intent == "action" else "success"
        assert result["tool_results"][0]["status"] == expected_status
    else:
        assert result.get("tool_results", []) == []


def test_graph_is_compiled_with_expected_nodes():
    assert isinstance(agent_graph, CompiledStateGraph)
    assert set(agent_graph.get_graph().nodes) == {
        "__start__",
        "supervisor",
        "rag_agent",
        "database_agent",
        "action_agent",
        "response_generator",
        "__end__",
    }


@pytest.mark.asyncio
async def test_mutation_language_takes_priority_over_database_nouns():
    result = await agent_graph.ainvoke(
        {
            "user_id": uuid.uuid4(),
            "role": RoleEnum.HR,
            "message": "Update this employee's department",
        }
    )
    assert result["intent"] == "action"
    assert "action_agent" in result["route_trace"]
