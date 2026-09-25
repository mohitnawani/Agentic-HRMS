from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import agent_graph
from app.agent.memory import ensure_conversation
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentSource

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    payload: AgentChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentChatResponse:
    conversation = await ensure_conversation(
        db, current_user.id, payload.conversation_id
    )
    result = await agent_graph.ainvoke(
        {
            "user_id": current_user.id,
            "role": current_user.role,
            "message": payload.message,
            # History is loaded server-side. Client-provided history is retained in
            # the request schema only for backward compatibility and is not trusted.
            "history": [],
            "conversation_id": conversation.id,
            "action_payload": payload.parameters,
        },
        context={"db": db},
    )
    tool_results = result.get("tool_results", [])
    data = tool_results[-1].get("data", {}) if tool_results else {}
    raw_sources = data.get("sources", []) if isinstance(data, dict) else []
    return AgentChatResponse(
        answer=result["final_answer"],
        intent=result["intent"],
        conversation_id=conversation.id,
        sources=[AgentSource.model_validate(source) for source in raw_sources],
    )
