"""Day 16 placeholder for permission-controlled HRMS actions."""

from app.agent.state import AgentState


def action_agent_node(state: AgentState) -> dict:
    return {
        "tool_results": [
            {
                "agent": "action",
                "status": "stub",
                "message": "Write actions will be connected after Day 17.",
            }
        ],
        "route_trace": ["action_agent"],
    }
