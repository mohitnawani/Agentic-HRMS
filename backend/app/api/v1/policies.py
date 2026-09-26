import asyncio
import re
import uuid
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.policy_document import PolicyDocumentRead
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])

# Cap proxied downloads so one huge file can't exhaust the worker.
MAX_POLICY_DOWNLOAD_BYTES = 50 * 1024 * 1024


def _download_policy_bytes(file_url: str) -> bytes:
    parsed = urlparse(file_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith("cloudinary.com")
    ):
        raise ValueError("Policy storage URL is invalid.")
    request = Request(file_url, headers={"User-Agent": "Agentic-HRMS/1.0"})
    with urlopen(request, timeout=20) as upstream:
        return upstream.read(MAX_POLICY_DOWNLOAD_BYTES + 1)


def _policy_filename(title: str) -> str:
    safe_title = re.sub(r'[\\/:*?"<>|]+', "_", title).strip(" .") or "policy"
    if not safe_title.lower().endswith(".pdf"):
        safe_title += ".pdf"
    return safe_title


@router.post(
    "",
    response_model=PolicyDocumentRead,
    dependencies=[Depends(require_permission("policy:write"))],
)
async def upload_policy(
    title: Annotated[str, Form()],
    category: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await policy_service.upload_policy(db, title, category, current_user.id, file)


@router.get(
    "",
    response_model=list[PolicyDocumentRead],
    dependencies=[Depends(require_permission("policy:read"))],
)
async def list_policies(
    db: Annotated[AsyncSession, Depends(get_db)], category: str | None = None
):
    return await policy_service.list_policies(db, category)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("policy:write"))],
)
async def delete_policy(
    doc_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await policy_service.delete_policy(db, doc_id)


@router.get(
    "/{doc_id}/download",
    dependencies=[Depends(require_permission("policy:read"))],
)
async def download_policy(
    doc_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    doc = await policy_service.get_policy(db, doc_id)
    try:
        contents = await asyncio.to_thread(_download_policy_bytes, doc.file_path)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The policy file could not be downloaded from storage.",
        ) from exc
    filename = _policy_filename(doc.title)
    disposition = (
        'attachment; filename="policy.pdf"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=contents,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
