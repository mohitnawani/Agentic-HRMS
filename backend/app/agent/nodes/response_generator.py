"""Final response node shared by every supervisor route."""

from app.agent.state import AgentState

GENERAL_RESPONSE = (
    "I can help with company policies, your HR data, and authorized HR actions."
)


def response_generator_node(state: AgentState) -> dict:
    results = state.get("tool_results", [])
    answer = results[-1]["message"] if results else GENERAL_RESPONSE
    return {"final_answer": answer, "route_trace": ["response_generator"]}
