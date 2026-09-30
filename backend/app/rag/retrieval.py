"""Vector retrieval for policy chunks."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document_chunk import DocumentChunk
from app.models.policy_document import PolicyDocument
from app.rag.embeddings import embed_policy_query


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_id: uuid.UUID
    title: str
    category: str
    chunk_index: int
    page_number: int
    content: str
    cosine_distance: float

    @property
    def similarity(self) -> float:
        return max(-1.0, min(1.0, 1.0 - self.cosine_distance))


async def retrieve_policy_chunks(
    db: AsyncSession,
    question: str,
    *,
    top_k: int | None = None,
    max_cosine_distance: float | None = None,
) -> list[RetrievedChunk]:
    """Return the closest policy chunks that pass the relevance threshold."""
    limit = top_k if top_k is not None else settings.rag_top_k
    if not 1 <= limit <= 10:
        raise ValueError("top_k must be between 1 and 10.")
    threshold = (
        max_cosine_distance
        if max_cosine_distance is not None
        else settings.rag_max_cosine_distance
    )
    query_vector = await embed_policy_query(question)
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label(
        "cosine_distance"
    )
    statement = (
        select(DocumentChunk, PolicyDocument, distance)
        .join(PolicyDocument, PolicyDocument.id == DocumentChunk.document_id)
        .where(distance <= threshold)
        .order_by(distance, DocumentChunk.id)
        .limit(limit)
    )
    rows = (await db.execute(statement)).all()
    return [
        RetrievedChunk(
            document_id=document.id,
            title=document.title,
            category=document.category,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            content=chunk.content,
            cosine_distance=float(row_distance),
        )
        for chunk, document, row_distance in rows
    ]
