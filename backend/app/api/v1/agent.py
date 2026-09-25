import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import agent_graph
from app.agent.memory import ensure_conversation, load_conversation_messages
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationMessage,
    AgentConversationResponse,
    AgentPendingInteraction,
    AgentSource,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get(
    "/conversations/{conversation_id}",
    response_model=AgentConversationResponse,
    response_model_exclude_unset=True,
)
async def get_agent_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentConversationResponse:
    conversation, messages = await load_conversation_messages(
        db, current_user.id, conversation_id
    )
    raw_pending = conversation.pending_action
    pending = None
    if raw_pending:
        raw_parameters = raw_pending.get("parameters", {})
        safe_parameters: dict[str, object] = {}
        if isinstance(raw_parameters, dict):
            allowed_keys = (
                ("title", "category")
                if raw_pending.get("tool") == "upload_policy"
                else ("employee_id",)
                if raw_pending.get("tool") == "update_employee"
                else ()
            )
            safe_parameters = {
                key: raw_parameters[key]
                for key in allowed_keys
                if raw_parameters.get(key)
            }
        pending = AgentPendingInteraction.model_validate(
            {
                "tool": raw_pending.get("tool", "unknown"),
                "stage": raw_pending.get("stage", "slots"),
                "missing_field": raw_pending.get("missing_field"),
                **({"parameters": safe_parameters} if safe_parameters else {}),
            }
        )
    return AgentConversationResponse(
        conversation_id=conversation.id,
        messages=[
            AgentConversationMessage(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in messages
        ],
        pending_interaction=pending,
    )


async def _invoke_agent(
    payload: AgentChatRequest,
    current_user: User,
    db: AsyncSession,
    conversation_id,
) -> dict:
    return await agent_graph.ainvoke(
        {
            "user_id": current_user.id,
            "role": current_user.role,
            "message": payload.message,
            # History is loaded server-side. Client-provided history is retained in
            # the request schema only for backward compatibility and is not trusted.
            "history": [],
            "conversation_id": conversation_id,
            "action_payload": payload.parameters,
        },
        context={"db": db},
    )


def _result_sources(result: dict) -> list[dict]:
    tool_results = result.get("tool_results", [])
    data = tool_results[-1].get("data", {}) if tool_results else {}
    return data.get("sources", []) if isinstance(data, dict) else []


def _sse(event: str, data: object) -> str:
    encoded = json.dumps(
        jsonable_encoder(data), ensure_ascii=False, separators=(",", ":")
    )
    return f"event: {event}\ndata: {encoded}\n\n"


def _answer_chunks(answer: str, words_per_chunk: int = 3) -> list[str]:
    words = re.findall(r"\S+\s*", answer)
    return [
        "".join(words[index : index + words_per_chunk])
        for index in range(0, len(words), words_per_chunk)
    ]


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    payload: AgentChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentChatResponse:
    conversation = await ensure_conversation(
        db, current_user.id, payload.conversation_id
    )
    result = await _invoke_agent(payload, current_user, db, conversation.id)
    raw_sources = _result_sources(result)
    return AgentChatResponse(
        answer=result["final_answer"],
        intent=result["intent"],
        conversation_id=conversation.id,
        sources=[AgentSource.model_validate(source) for source in raw_sources],
    )


@router.post("/chat/stream")
async def stream_chat_with_agent(
    payload: AgentChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream one authenticated agent turn as server-sent events."""
    conversation = await ensure_conversation(
        db, current_user.id, payload.conversation_id
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield _sse("meta", {"conversation_id": conversation.id})
            yield _sse("status", {"message": "Working on your request..."})
            result = await _invoke_agent(payload, current_user, db, conversation.id)
            for tool_result in result.get("tool_results", []):
                yield _sse("tool", tool_result)
            for chunk in _answer_chunks(result["final_answer"]):
                yield _sse("token", {"text": chunk})
                await asyncio.sleep(0)
            sources = _result_sources(result)
            if sources:
                yield _sse("sources", {"items": sources})
            yield _sse(
                "done",
                {
                    "intent": result["intent"],
                    "conversation_id": conversation.id,
                },
            )
        except asyncio.CancelledError:
            await db.rollback()
            raise
        except Exception:  # noqa: BLE001 - stream errors must become safe SSE events
            await db.rollback()
            yield _sse(
                "error",
                {"message": "The assistant could not complete this request."},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
