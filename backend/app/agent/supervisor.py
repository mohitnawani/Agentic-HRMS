"""Deterministic request classifier used by the Day 16 supervisor node."""

import re
from typing import Literal

from app.agent.state import AgentIntent, AgentState

AGENT_NODE_NAMES = Literal[
    "rag_agent", "database_agent", "action_agent", "response_generator"
]

ACTION_PATTERNS = (
    r"\b(create|add|update|change|edit|correct|fix|delete|remove|upload|publish|post)\b",
    r"\b(approve|reject|cancel)\b.*\b(leave|request)\b",
    r"\bapply\b.*\bleave\b",
    r"\b(check[ -]?in|check[ -]?out)\b",
)
DATABASE_PATTERNS = (
    r"\b(show|view|list|get)\b.*\baudit\b",
    r"\b(holiday|holidays|announcement|announcements)\b",
    r"\b(leave history|leave requests|pending leave|leave approved|leave rejected)\b",
    r"\b(manage|review)\b.*\bleaves?\b",
    r"\b(how many|remaining)\b.*\b(leave|leaves|days)\b",
    r"\b(how many|number of|total|count|list|show|available)\b.*\bpolic(?:y|ie|ies)\b",
    r"\b(leave balance|leave history|attendance|employee details)\b",
    r"\b(list|show|find|get)\b.*\b(employee|employees|department|attendance)\b",
    r"\b(view|show|get|find)\b.*\bemployees?\b.*\b(details?|profile|information)\b",
    r"\b(tell|give)\b.*\b(details?|information|about)\b.*\bemployees?\b",
    (
        r"^(?!.*\b(policy|policies|leave|attendance|holiday|department|designation|"
        r"announcement|user|account)\b).*\b(show|view|find|get|tell|give)\b.*"
        r"\b(details?|profile|information|about)\b"
    ),
    r"\b(how many|number of|total|count|list|show|get)\b.*\b(departments?|designations?|users?|employees?)\b",
    r"\b(show|open|view)\b.*\bdashboard\b",
    r"\borg(ani[sz]ation)?\b.*\b(stats|statistics|overview|summary)\b",
    r"\b(my profile|my attendance|my leaves)\b",
    (
        r"\bmy\b.*\b(profile|details?|information|name|nmae|employee\s*(id|code)|"
        r"email|emial|phone|phoen|mobile|joining|joined|role|department|designation|"
        r"birth|dob|gender|address|city|emergency|account\s*status)\b"
    ),
)
RAG_PATTERNS = (
    r"\b(polic(?:y|ie|ies)|handbook|guideline|guidelines|code of conduct)\b",
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
    classified = classify_intent(state["message"])
    # Once a workflow starts, every message belongs to it until completion or
    # explicit cancellation. This prevents field values from activating other
    # nodes and keeps unrelated questions from silently changing the flow.
    intent: AgentIntent = "action" if state.get("pending_action") else classified
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
