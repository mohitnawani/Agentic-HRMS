import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy_document import PolicyDocument

UPLOAD_DIR = Path("uploads/policies")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def upload_policy(
    db: AsyncSession, title: str, category: str, uploaded_by: uuid.UUID, file: UploadFile
) -> PolicyDocument:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files allowed")

    file_id = uuid.uuid4()
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    doc = PolicyDocument(
        title=title, category=category, file_path=str(file_path), uploaded_by=uploaded_by
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