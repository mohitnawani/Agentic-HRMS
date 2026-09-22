import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import cloudinary
import cloudinary.uploader

from app.core.config import settings
from app.models.policy_document import PolicyDocument


def _ensure_configured() -> None:
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
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
    db: AsyncSession, title: str, category: str, uploaded_by: uuid.UUID, file: UploadFile
) -> PolicyDocument:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files allowed")
    _ensure_configured()

    contents = await file.read()
    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="hrms/policies",
            resource_type="raw",
            public_id=f"{uuid.uuid4()}_{file.filename}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cloudinary upload failed: {exc}"
        )

    doc = PolicyDocument(
        title=title, category=category, file_path=result["secure_url"], uploaded_by=uploaded_by
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_policies(db: AsyncSession, category: str | None = None) -> list[PolicyDocument]:
    query = select(PolicyDocument)
    if category:
        query = query.where(PolicyDocument.category == category)
    result = await db.execute(query.order_by(PolicyDocument.created_at.desc()))
    return list(result.scalars().all())


async def get_policy(db: AsyncSession, doc_id: uuid.UUID) -> PolicyDocument:
    result = await db.execute(select(PolicyDocument).where(PolicyDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy document not found")
    return doc