"""Deterministic request classifier used by the Day 16 supervisor node."""

import re
from typing import Literal

from app.agent.state import AgentIntent, AgentState

AGENT_NODE_NAMES = Literal[
    "rag_agent", "database_agent", "action_agent", "response_generator"
]

ACTION_PATTERNS = (
    r"\b(create|add|update|change|edit|delete|remove)\b",
    r"\b(approve|reject|cancel)\b.*\b(leave|request)\b",
    r"\bapply\b.*\bleave\b",
    r"\b(check[ -]?in|check[ -]?out)\b",
)
DATABASE_PATTERNS = (
    r"\b(how many|remaining)\b.*\b(leave|leaves|days)\b",
    r"\b(leave balance|leave history|attendance|employee details)\b",
    r"\b(list|show|find|get)\b.*\b(employee|employees|department|attendance)\b",
    r"\b(my profile|my attendance|my leaves)\b",
)
RAG_PATTERNS = (
    r"\b(policy|policies|handbook|guideline|guidelines|code of conduct)\b",
    r"\b(work[ -]?from[ -]?home|wfh|benefits|travel policy)\b",
)


def classify_intent(message: str) -> AgentIntent:
    """Classify broad intent without allowing generated text to select tools."""
    normalized = " ".join(message.lower().split())
    # Mutation language takes priority over nouns such as employee or leave.
    if any(re.search(pattern, normalized) for pattern in ACTION_PATTERNS):
        return "action"
    if any(re.search(pattern, normalized) for pattern in DATABASE_PATTERNS):
        return "database"
    if any(re.search(pattern, normalized) for pattern in RAG_PATTERNS):
        return "rag"
    return "general"


def supervisor_node(state: AgentState) -> dict:
    intent: AgentIntent = (
        "action" if state.get("pending_action") else classify_intent(state["message"])
    )
    return {
        "intent": intent,
        "route_trace": ["supervisor"],
    }


def route_from_supervisor(state: AgentState) -> AGENT_NODE_NAMES:
    routes: dict[AgentIntent, AGENT_NODE_NAMES] = {
        "rag": "rag_agent",
        "database": "database_agent",
        "action": "action_agent",
        "general": "response_generator",
    }
    return routes[state["intent"]]
