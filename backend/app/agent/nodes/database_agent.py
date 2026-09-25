"""Day 16 placeholder for read-only structured HRMS queries."""

from app.agent.state import AgentState


def database_agent_node(state: AgentState) -> dict:
    return {
        "tool_results": [
            {
                "agent": "database",
                "status": "stub",
                "message": "Read-only HRMS tools will be connected in Day 17.",
            }
        ],
        "route_trace": ["database_agent"],
    }
