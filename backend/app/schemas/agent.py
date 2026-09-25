import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.agent.state import AgentIntent


class AgentHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    history: list[AgentHistoryMessage] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Message must contain at least 2 characters.")
        return normalized


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
    sources: list[AgentSource] = Field(default_factory=list)
