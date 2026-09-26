"""Safely normalize unclear user questions before supervisor routing."""

import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.state import AgentState
from app.agent.supervisor import classify_intent
from app.core.config import settings

CONFIRMATION_WORDS = {"yes", "y", "confirm", "confirmed", "proceed"}
CANCELLATION_WORDS = {"no", "n", "cancel", "stop", "abort"}

COMMON_CORRECTIONS = {
    "annoucement": "announcement",
    "annoucements": "announcements",
    "aply": "apply",
    "aplly": "apply",
    "aprove": "approve",
    "attendence": "attendance",
    "balnce": "balance",
    "chek": "check",
    "delte": "delete",
    "detials": "details",
    "employe": "employee",
    "employess": "employees",
    "emploues": "employees",
    "leav": "leave",
    "polcy": "policy",
    "polcies": "policies",
    "polices": "policies",
    "rejct": "reject",
    "shwo": "show",
    "sumarize": "summarize",
    "summry": "summary",
    "teh": "the",
    "toal": "total",
    "wat": "what",
    "wht": "what",
    "whcih": "which",
}

PROTECTED_PATTERN = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d+(?:\.\d+)?\b"
)


class RewrittenQuestion(BaseModel):
    rewritten_question: str = Field(min_length=2, max_length=2_000)


class QueryRewriteError(RuntimeError):
    """The optional LLM query rewrite could not be completed."""


REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Rewrite the user's HRMS question with corrected spelling and clear grammar.
Keep the exact meaning and requested operation. Never add facts, assumptions, or a new
action. Preserve every person name, email, UUID, date, number, quoted value, and policy
name exactly. Return only the rewritten question in the structured field.""",
        ),
        ("human", "Original user message: {message}"),
    ]
)


def correct_common_misspellings(message: str) -> str:
    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, COMMON_CORRECTIONS)) + r")\b",
        re.IGNORECASE,
    )
    return pattern.sub(
        lambda match: COMMON_CORRECTIONS[match.group(0).lower()], message
    )


def _preserves_protected_values(original: str, rewritten: str) -> bool:
    return all(
        rewritten.count(value) >= original.count(value)
        for value in PROTECTED_PATTERN.findall(original)
    )


async def rewrite_question(message: str) -> str:
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        return message
    model = ChatGoogleGenerativeAI(
        model=settings.rag_generation_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        max_retries=1,
        request_timeout=min(settings.rag_generation_timeout_seconds, 10),
    )
    chain = REWRITE_PROMPT | model.with_structured_output(
        RewrittenQuestion, method="json_schema"
    )
    try:
        result = await chain.ainvoke({"message": message})
        rewritten = " ".join(result.rewritten_question.split())
    except Exception as exc:
        raise QueryRewriteError("Query rewriting failed.") from exc
    return rewritten


async def query_rewriter_node(state: AgentState) -> dict:
    original = state["message"]
    normalized = " ".join(original.split())
    answer = normalized.lower()
    if (
        state.get("pending_action")
        or answer in CONFIRMATION_WORDS
        or answer in CANCELLATION_WORDS
    ):
        return {
            "original_message": original,
            "message": normalized,
            "route_trace": ["query_rewriter"],
        }

    corrected = correct_common_misspellings(normalized)
    corrected_intent = classify_intent(corrected)
    # Deterministic action correction is safer than allowing an LLM to rewrite
    # names or action parameters. Permissions are still checked by every tool.
    if corrected_intent == "action":
        return {
            "original_message": original,
            "message": corrected,
            "route_trace": ["query_rewriter"],
        }

    # Clear, correctly routed questions do not need another model call.
    if corrected == normalized:
        rewritten = corrected
    else:
        try:
            candidate = await rewrite_question(corrected)
        except QueryRewriteError:
            candidate = corrected
        candidate_intent = classify_intent(candidate)
        safe_length = 2 <= len(candidate) <= min(2_000, len(corrected) * 2 + 100)
        if (
            safe_length
            and _preserves_protected_values(corrected, candidate)
            and not (candidate_intent == "action" and corrected_intent != "action")
        ):
            rewritten = candidate
        else:
            rewritten = corrected

    return {
        "original_message": original,
        "message": rewritten,
        "route_trace": ["query_rewriter"],
    }
