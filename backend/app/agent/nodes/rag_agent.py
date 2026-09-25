"""Day 16 placeholder for the policy RAG agent."""

from app.agent.state import AgentState


def rag_agent_node(state: AgentState) -> dict:
    return {
        "tool_results": [
            {
                "agent": "rag",
                "status": "stub",
                "message": "Policy retrieval will be connected in Day 17.",
            }
        ],
        "route_trace": ["rag_agent"],
    }
