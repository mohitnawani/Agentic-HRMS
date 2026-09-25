"""Policy RAG Agent backed by the Day 15 grounded retrieval pipeline."""

from langgraph.runtime import Runtime

from app.agent.state import AgentRuntimeContext, AgentState
from app.core.permissions import has_permission
from app.models.role import RoleEnum
from app.rag.embeddings import PolicyEmbeddingError
from app.rag.generation import GroundedGenerationError, generate_grounded_answer
from app.rag.retrieval import retrieve_policy_chunks


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

    chunks = await retrieve_policy_chunks(db, state["message"])
    generated = await generate_grounded_answer(state["message"], chunks)
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
