"""Shared state contracts for the Agentic HRMS LangGraph."""

import operator
import uuid
from typing import Annotated, Literal, NotRequired, Required, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import RoleEnum

AgentIntent = Literal["rag", "database", "action", "general"]


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class RetrievedContext(TypedDict):
    document_id: str
    title: str
    category: str
    page_number: int
    chunk_index: int
    content: str
    similarity: float


class AgentToolResult(TypedDict):
    agent: AgentIntent
    status: Literal[
        "stub",
        "success",
        "denied",
        "error",
        "needs_input",
        "confirmation_required",
        "cancelled",
    ]
    message: str
    tool: NotRequired[str]
    data: NotRequired[dict[str, object] | list[dict[str, object]]]


class AgentRuntimeContext(TypedDict):
    """Non-serializable dependencies available only during one graph run."""

    db: AsyncSession


class AgentState(TypedDict, total=False):
    """Complete state shared by graph nodes during one authenticated request."""

    # These values must be supplied by authentication code, never by the LLM.
    user_id: Required[uuid.UUID]
    role: Required[RoleEnum]
    message: Required[str]
    history: Annotated[list[ConversationMessage], operator.add]
    conversation_id: uuid.UUID
    conversation_summary: str
    pending_action: dict[str, object] | None
    memory_user_message: str
    action_payload: dict[str, object]

    intent: AgentIntent
    retrieved_context: Annotated[list[RetrievedContext], operator.add]
    tool_results: Annotated[list[AgentToolResult], operator.add]
    route_trace: Annotated[list[str], operator.add]
    final_answer: str
    error: str


class AgentInput(TypedDict, total=False):
    user_id: Required[uuid.UUID]
    role: Required[RoleEnum]
    message: Required[str]
    history: NotRequired[list[ConversationMessage]]
    conversation_id: NotRequired[uuid.UUID]
    action_payload: NotRequired[dict[str, object]]


class AgentOutput(TypedDict, total=False):
    user_id: uuid.UUID
    role: RoleEnum
    intent: AgentIntent
    retrieved_context: list[RetrievedContext]
    tool_results: list[AgentToolResult]
    route_trace: list[str]
    final_answer: str
    error: str
    conversation_id: uuid.UUID
    pending_action: dict[str, object] | None
