"""Persistent, user-scoped short-term memory for agent conversations."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import ConversationMessage
from app.models.agent_conversation import AgentConversation, AgentMessage

RECENT_MESSAGE_LIMIT = 10
SUMMARY_CHARACTER_LIMIT = 2000


async def ensure_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
) -> AgentConversation:
    """Return an owned conversation, creating one when no ID was supplied."""
    if conversation_id is None:
        conversation = AgentConversation(user_id=user_id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    conversation = await db.get(AgentConversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        # Use one response for missing and foreign IDs to avoid leaking ownership.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


async def load_conversation_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> tuple[list[ConversationMessage], str, dict | None]:
    conversation = await ensure_conversation(db, user_id, conversation_id)
    statement = (
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
        .limit(RECENT_MESSAGE_LIMIT)
    )
    messages = list(reversed((await db.scalars(statement)).all()))
    history: list[ConversationMessage] = [
        {"role": message.role, "content": message.content}  # type: ignore[typeddict-item]
        for message in messages
    ]
    return history, conversation.summary or "", conversation.pending_action


def _rolling_summary(messages: list[AgentMessage]) -> str | None:
    if len(messages) <= RECENT_MESSAGE_LIMIT:
        return None
    older_messages = messages[:-RECENT_MESSAGE_LIMIT]
    compact = "\n".join(
        f"{message.role.title()}: {' '.join(message.content.split())}"
        for message in older_messages
    )
    # Preserve the newest part of older context when the extractive summary grows.
    return compact[-SUMMARY_CHARACTER_LIMIT:]


async def save_conversation_exchange(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message: str,
    assistant_message: str,
    pending_action: dict | None,
) -> None:
    statement = (
        select(AgentConversation)
        .where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user_id,
        )
        .with_for_update()
    )
    conversation = await db.scalar(statement)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    db.add_all(
        [
            AgentMessage(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            ),
            AgentMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_message,
            ),
        ]
    )
    conversation.pending_action = jsonable_encoder(pending_action)
    conversation.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.flush()

    all_messages = list(
        (
            await db.scalars(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == conversation.id)
                .order_by(AgentMessage.created_at, AgentMessage.id)
            )
        ).all()
    )
    conversation.summary = _rolling_summary(all_messages)
    await db.commit()
