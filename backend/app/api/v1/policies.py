import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.policy_document import PolicyDocumentRead
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", response_model=PolicyDocumentRead, dependencies=[Depends(require_permission("policy:write"))])
async def upload_policy(
    title: str = Form(...), category: str = Form(...), file: UploadFile = File(...),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await policy_service.upload_policy(db, title, category, current_user.id, file)


@router.get("", response_model=list[PolicyDocumentRead], dependencies=[Depends(require_permission("policy:read"))])
async def list_policies(category: str | None = None, db: AsyncSession = Depends(get_db)):
    return await policy_service.list_policies(db, category)


@router.get("/{doc_id}/download", dependencies=[Depends(require_permission("policy:read"))])
async def download_policy(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await policy_service.get_policy(db, doc_id)
    return FileResponse(doc.file_path, filename=doc.title)