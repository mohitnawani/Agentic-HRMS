import uuid

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import agent_graph
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
async def test_graph_routes_requests(message, expected_intent, expected_node):
    user_id = uuid.uuid4()
    result = await agent_graph.ainvoke(
        {
            "user_id": user_id,
            "role": RoleEnum.EMPLOYEE,
            "message": message,
            "history": [],
        }
    )

    assert result["user_id"] == user_id
    assert result["role"] == RoleEnum.EMPLOYEE
    assert result["intent"] == expected_intent
    assert result["route_trace"][0] == "supervisor"
    assert result["route_trace"][-1] == "response_generator"
    assert bool(result.get("final_answer"))
    if expected_node:
        assert expected_node in result["route_trace"]
        assert result["tool_results"][0]["status"] == "stub"
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
