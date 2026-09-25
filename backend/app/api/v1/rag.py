from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.rag.embeddings import PolicyEmbeddingError
from app.rag.generation import GroundedGenerationError, generate_grounded_answer
from app.rag.retrieval import retrieve_policy_chunks
from app.schemas.rag import PolicyAnswerSource, PolicyAskRequest, PolicyAskResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/ask",
    response_model=PolicyAskResponse,
    dependencies=[Depends(require_permission("policy:read"))],
)
async def ask_policy_question(
    payload: PolicyAskRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> PolicyAskResponse:
    try:
        chunks = await retrieve_policy_chunks(db, payload.question, top_k=payload.top_k)
        generated = await generate_grounded_answer(payload.question, chunks)
    except PolicyEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except GroundedGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    sources = [
        PolicyAnswerSource(
            source_number=number,
            document_id=chunks[number - 1].document_id,
            title=chunks[number - 1].title,
            category=chunks[number - 1].category,
            page_number=chunks[number - 1].page_number,
            chunk_index=chunks[number - 1].chunk_index,
            similarity=round(chunks[number - 1].similarity, 4),
        )
        for number in generated.source_numbers
    ]
    return PolicyAskResponse(answer=generated.answer, sources=sources)
