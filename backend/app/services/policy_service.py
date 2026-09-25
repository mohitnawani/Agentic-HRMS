import asyncio
import logging
import uuid

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.policy_document import PolicyDocument
from app.rag.embeddings import PolicyEmbeddingError
from app.rag.ingestion import (
    PolicyExtractionError,
    chunk_pages,
    extract_pdf_pages,
    store_policy_chunks,
)

logger = logging.getLogger(__name__)


def _ensure_configured() -> None:
    if not (
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloudinary is not configured (set CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET)",
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


async def upload_policy(
    db: AsyncSession,
    title: str,
    category: str,
    uploaded_by: uuid.UUID,
    file: UploadFile,
) -> PolicyDocument:
    _ensure_configured()

    contents = await file.read()
    try:
        pages = await asyncio.to_thread(extract_pdf_pages, contents)
        chunks = chunk_pages(pages)
    except PolicyExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            contents,
            folder="hrms/policies",
            resource_type="raw",
            public_id=str(uuid.uuid4()),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Policy file storage is temporarily unavailable.",
        ) from exc

    public_id = result.get("public_id")
    secure_url = result.get("secure_url")
    if not public_id or not secure_url:
        if public_id:
            await _remove_uploaded_policy(public_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Policy file storage returned an invalid response.",
        )

    doc = PolicyDocument(
        title=title, category=category, file_path=secure_url, uploaded_by=uploaded_by
    )
    try:
        db.add(doc)
        await db.flush()
        await store_policy_chunks(db, doc.id, chunks)
        await db.commit()
        await db.refresh(doc)
        return doc
    except PolicyEmbeddingError as exc:
        await db.rollback()
        await _remove_uploaded_policy(public_id)
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "GEMINI_API_KEY" in str(exc)
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception:
        await db.rollback()
        await _remove_uploaded_policy(public_id)
        raise


async def _remove_uploaded_policy(public_id: str) -> None:
    """Best-effort compensation when database ingestion fails."""
    try:
        await asyncio.to_thread(
            cloudinary.uploader.destroy, public_id, resource_type="raw", invalidate=True
        )
    except Exception:
        # Preserve the original ingestion error; cleanup can be retried manually.
        logger.exception("Failed to remove orphaned Cloudinary policy %s", public_id)


async def list_policies(
    db: AsyncSession, category: str | None = None
) -> list[PolicyDocument]:
    query = select(PolicyDocument)
    if category:
        query = query.where(PolicyDocument.category == category)
    result = await db.execute(query.order_by(PolicyDocument.created_at.desc()))
    return list(result.scalars().all())


async def get_policy(db: AsyncSession, doc_id: uuid.UUID) -> PolicyDocument:
    result = await db.execute(select(PolicyDocument).where(PolicyDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy document not found"
        )
    return doc
