"""Policy RAG Agent backed by the Day 15 grounded retrieval pipeline."""

import re

from langgraph.runtime import Runtime

from app.agent.state import AgentRuntimeContext, AgentState
from app.agent.tools.read_tools import get_policy_catalog, get_policy_summaries
from app.core.permissions import has_permission
from app.models.role import RoleEnum
from app.rag.embeddings import PolicyEmbeddingError
from app.rag.generation import GroundedGenerationError, generate_grounded_answer
from app.rag.retrieval import retrieve_policy_chunks


async def _policy_catalog_fallback(state: AgentState, db) -> dict:
    catalog = await get_policy_catalog(state, db)
    policies = catalog["policies"]
    if not policies:
        message = (
            "No policy documents are available yet. Ask HR or an admin to upload "
            "a policy document first."
        )
    else:
        names = ", ".join(
            f"{item['title']} ({item['category']})" for item in policies[:5]
        )
        remaining = len(policies) - 5
        suffix = f", and {remaining} more" if remaining > 0 else ""
        message = (
            "I couldn't find a specific policy passage that answers that question. "
            f"The available policy documents are: {names}{suffix}. "
            "Try asking about a specific rule or topic from one of these documents."
        )
    return {
        "tool_result": {
            "agent": "rag",
            "status": "success",
            "tool": "policy_rag",
            "message": message,
            "data": {"sources": [], "catalog": catalog},
        },
        "retrieved_context": [],
    }


async def _policy_summary_response(state: AgentState, db) -> dict:
    result = await get_policy_summaries(state, db, state["message"])
    summaries = result["summaries"]
    if result["selection_required"]:
        names = ", ".join(
            f"{item['title']} ({item['category']})" for item in result["policies"][:10]
        )
        message = f"Which policy should I summarize? Available policies: {names}."
    elif not summaries:
        message = "No policy documents are available to summarize yet."
    elif len(summaries) == 1:
        item = summaries[0]
        message = f"Summary of {item['title']}:\n\n{item['summary']}"
    else:
        message = "\n\n".join(
            f"{item['title']} ({item['category']}):\n{item['summary']}"
            for item in summaries
        )
    return {
        "tool_result": {
            "agent": "rag",
            "status": "success",
            "tool": "policy_summary",
            "message": message,
            "data": result,
        },
        "retrieved_context": [],
    }


async def run_policy_rag(state: AgentState, db) -> dict:
    role = RoleEnum(state["role"])
    if not has_permission(role, "policy:read"):
        return {
            "tool_result": {
                "agent": "rag",
                "status": "denied",
                "tool": "policy_rag",
                "message": "Your role cannot access company policy documents.",
            },
            "retrieved_context": [],
        }

    if re.search(
        r"\b(summary|summarize|summarise|overview)\b", state["message"], re.IGNORECASE
    ):
        return await _policy_summary_response(state, db)

    chunks = await retrieve_policy_chunks(db, state["message"])
    if not chunks:
        return await _policy_catalog_fallback(state, db)
    history_lines = [
        f"{item['role'].title()}: {item['content']}"
        for item in state.get("history", [])[-10:]
    ]
    if state.get("conversation_summary"):
        history_lines.insert(0, f"Earlier summary: {state['conversation_summary']}")
    if history_lines:
        generated = await generate_grounded_answer(
            state["message"],
            chunks,
            conversation_context="\n".join(history_lines),
        )
    else:
        generated = await generate_grounded_answer(state["message"], chunks)
    if not generated.source_numbers:
        return await _policy_catalog_fallback(state, db)
    cited = [chunks[number - 1] for number in generated.source_numbers]
    sources = [
        {
            "source_number": number,
            "document_id": str(chunks[number - 1].document_id),
            "title": chunks[number - 1].title,
            "category": chunks[number - 1].category,
            "page_number": chunks[number - 1].page_number,
            "chunk_index": chunks[number - 1].chunk_index,
            "similarity": round(chunks[number - 1].similarity, 4),
        }
        for number in generated.source_numbers
    ]
    context = [
        {
            "document_id": str(chunk.document_id),
            "title": chunk.title,
            "category": chunk.category,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "similarity": round(chunk.similarity, 4),
        }
        for chunk in cited
    ]
    return {
        "tool_result": {
            "agent": "rag",
            "status": "success",
            "tool": "policy_rag",
            "message": generated.answer,
            "data": {"sources": sources},
        },
        "retrieved_context": context,
    }


async def rag_agent_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    try:
        result = await run_policy_rag(state, runtime.context["db"])
    except (PolicyEmbeddingError, GroundedGenerationError):
        result = {
            "tool_result": {
                "agent": "rag",
                "status": "error",
                "tool": "policy_rag",
                "message": "The policy assistant is temporarily unavailable.",
            },
            "retrieved_context": [],
        }
    return {
        "tool_results": [result["tool_result"]],
        "retrieved_context": result["retrieved_context"],
        "route_trace": ["rag_agent"],
    }
