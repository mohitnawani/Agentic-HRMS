"""LangGraph nodes that load and persist user-scoped conversation memory."""

from langgraph.runtime import Runtime

from app.agent.memory import load_conversation_memory, save_conversation_exchange
from app.agent.state import AgentRuntimeContext, AgentState


async def load_memory_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    conversation_id = state.get("conversation_id")
    if conversation_id is None:
        return {}
    history, summary, pending_action = await load_conversation_memory(
        runtime.context["db"], state["user_id"], conversation_id
    )
    return {
        "history": history,
        "conversation_summary": summary,
        "pending_action": pending_action,
    }


async def save_memory_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    conversation_id = state.get("conversation_id")
    if conversation_id is None:
        return {}
    await save_conversation_exchange(
        runtime.context["db"],
        state["user_id"],
        conversation_id,
        state.get("memory_user_message", state["message"]),
        state["final_answer"],
        state.get("pending_action"),
    )
    return {}
