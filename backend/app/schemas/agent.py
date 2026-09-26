import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.agent.state import AgentIntent


class AgentHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: uuid.UUID | None = None
    history: list[AgentHistoryMessage] = Field(default_factory=list, max_length=20)
    parameters: dict[str, object] = Field(default_factory=dict, max_length=20)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Message must contain at least 2 characters.")
        return normalized

    @field_validator("parameters")
    @classmethod
    def bound_parameters(cls, value: dict[str, object]) -> dict[str, object]:
        for key, item in value.items():
            if len(key) > 64 or len(str(item)) > 2000:
                raise ValueError("Action parameters are too large.")
        return value


class AgentSource(BaseModel):
    source_number: int
    document_id: uuid.UUID
    title: str
    category: str
    page_number: int
    chunk_index: int
    similarity: float


class AgentChatResponse(BaseModel):
    answer: str
    intent: AgentIntent
    conversation_id: uuid.UUID
    sources: list[AgentSource] = Field(default_factory=list)


class AgentConversationMessage(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AgentPendingInteraction(BaseModel):
    tool: str
    stage: Literal["slots", "confirmation"]
    missing_field: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


class AgentConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    messages: list[AgentConversationMessage]
    pending_interaction: AgentPendingInteraction | None = None
