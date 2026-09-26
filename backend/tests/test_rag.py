import uuid
from io import BytesIO
from itertools import pairwise

import pytest
from pydantic import SecretStr
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import delete, select

from app.api.v1 import policies as policies_api
from app.core.security import hash_password
from app.db.session import async_session
from app.models.document_chunk import EMBEDDING_DIMENSIONS, DocumentChunk
from app.models.policy_document import PolicyDocument
from app.models.role import RoleEnum
from app.models.user import User
from app.rag import embeddings as embedding_module
from app.rag.embeddings import (
    PolicyEmbeddingError,
    embed_policy_texts,
    validate_vectors,
)
from app.rag.ingestion import (
    ExtractedPage,
    PolicyExtractionError,
    TextChunk,
    chunk_pages,
    extract_pdf_pages,
    store_policy_chunks,
)
from app.services import policy_service


def make_pdf(page_texts: list[str | None], *, encrypted: bool = False) -> bytes:
    """Build actual PDF bytes without an extra fixture-generation dependency."""
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        if text is None:
            continue
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extract_preserves_text_order_and_original_page_numbers():
    pages = extract_pdf_pages(
        make_pdf(["Casual leave: 12 days.", None, "Sick leave: 6 days."])
    )
    assert [page.page_number for page in pages] == [1, 3]
    assert [page.text for page in pages] == [
        "Casual leave: 12 days.",
        "Sick leave: 6 days.",
    ]


@pytest.mark.parametrize(
    "contents, message",
    [
        (b"", "empty"),
        (b"not a pdf", "not a valid PDF"),
        (b"%PDF-1.7\nbroken", "could not be read"),
    ],
)
def test_rejects_empty_invalid_and_corrupt_files(contents, message):
    with pytest.raises(PolicyExtractionError, match=message):
        extract_pdf_pages(contents)


def test_rejects_encrypted_pdf():
    with pytest.raises(PolicyExtractionError, match="Password-protected"):
        extract_pdf_pages(make_pdf(["Private policy"], encrypted=True))


@pytest.mark.parametrize("page_texts", [[], [None], ["   "]])
def test_rejects_pdf_without_extractable_text(page_texts):
    with pytest.raises(PolicyExtractionError, match="No readable text"):
        extract_pdf_pages(make_pdf(page_texts))


def test_chunks_preserve_pages_and_document_order():
    pages = extract_pdf_pages(
        make_pdf(["Leave policy. " * 20, None, "Sick leave: 6 days."])
    )
    chunks = chunk_pages(pages, chunk_size=60, chunk_overlap=10)
    assert len(chunks) > 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.page_number == 1 for c in chunks[:-1])
    assert chunks[-1].page_number == 3
    assert chunks[-1].content == "Sick leave: 6 days."
    assert all(0 < len(c.content) <= 60 for c in chunks)


def test_character_fallback_overlaps_without_losing_text():
    text = "abcdefghijklmnopqrstuvwxyz0123456789"
    chunks = chunk_pages([ExtractedPage(1, text)], chunk_size=10, chunk_overlap=3)
    for left, right in pairwise(chunks):
        assert left.content[-3:] == right.content[:3]
    assert chunks[0].content + "".join(c.content[3:] for c in chunks[1:]) == text


def test_zero_overlap_and_unicode():
    text = "छुट्टीनीति" * 10
    chunks = chunk_pages([ExtractedPage(2, text)], chunk_size=15, chunk_overlap=0)
    assert "".join(c.content for c in chunks) == text
    assert all(len(c.content) <= 15 for c in chunks)


def test_chunking_skips_empty_pages():
    assert chunk_pages([]) == []
    assert chunk_pages([ExtractedPage(1, " \n ")]) == []


@pytest.mark.parametrize(
    "size, overlap", [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)]
)
def test_invalid_chunk_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages([], chunk_size=size, chunk_overlap=overlap)


@pytest.mark.parametrize(
    "vectors,count,message",
    [
        ([], 1, "count"),
        ([[1.0]], 1, "dimensions"),
        ([[0.0] * EMBEDDING_DIMENSIONS], 1, "zero vector"),
        ([[float("nan")] * EMBEDDING_DIMENSIONS], 1, "numeric"),
        ([[float("inf")] * EMBEDDING_DIMENSIONS], 1, "numeric"),
    ],
)
def test_rejects_invalid_embedding_output(vectors, count, message):
    with pytest.raises(PolicyEmbeddingError, match=message):
        validate_vectors(vectors, count)


@pytest.mark.asyncio
async def test_embedding_adapter_formats_documents_and_batches(monkeypatch):
    calls: list[list[str]] = []
    closed = {"async": False, "sync": False}

    class FakeAsyncClient:
        async def aclose(self):
            closed["async"] = True

    class FakeClient:
        aio = FakeAsyncClient()

        def close(self):
            closed["sync"] = True

    class FakeEmbedder:
        client = FakeClient()

        def __init__(self, **kwargs):
            assert kwargs["model"] == "gemini-embedding-2"
            assert kwargs["output_dimensionality"] == EMBEDDING_DIMENSIONS

        async def aembed_documents(self, texts, *, batch_size):
            assert batch_size == 16
            calls.append(texts)
            return [[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts]

    monkeypatch.setattr(embedding_module, "GeminiPolicyEmbeddings", FakeEmbedder)
    monkeypatch.setattr(
        embedding_module.settings, "gemini_api_key", SecretStr("test-key")
    )

    vectors = await embed_policy_texts(
        [f"chunk {i}" for i in range(17)], "Leave Policy"
    )

    assert len(vectors) == 17
    assert [len(batch) for batch in calls] == [16, 1]
    assert calls[0][0] == "title: Leave Policy | text: chunk 0"
    assert closed == {"async": True, "sync": True}


@pytest.mark.asyncio
async def test_store_policy_chunks_replaces_existing_rows(monkeypatch):
    async def fake_embed(texts, title):
        assert title == "Test Policy"
        return [
            [float(index + 1)] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
            for index, _ in enumerate(texts)
        ]

    monkeypatch.setattr("app.rag.ingestion.embed_policy_texts", fake_embed)

    async with async_session() as db:
        user = User(
            id=uuid.uuid4(),
            email=f"rag_{uuid.uuid4().hex}@test.local",
            hashed_password="unused",
            role=RoleEnum.ADMIN,
        )
        db.add(user)
        await db.flush()
        policy = PolicyDocument(
            id=uuid.uuid4(),
            title="Test Policy",
            category="test",
            file_path="https://example.test/policy.pdf",
            uploaded_by=user.id,
        )
        db.add(policy)
        await db.flush()

        count = await store_policy_chunks(
            db,
            policy.id,
            [TextChunk(0, 1, "First"), TextChunk(1, 2, "Second")],
        )
        assert count == 2

        count = await store_policy_chunks(
            db, policy.id, [TextChunk(0, 3, "Replacement")]
        )
        assert count == 1
        rows = list(
            (
                await db.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == policy.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
        )
        assert [(row.chunk_index, row.page_number, row.content) for row in rows] == [
            (0, 3, "Replacement")
        ]
        assert len(rows[0].embedding) == EMBEDDING_DIMENSIONS
        await db.rollback()


@pytest.mark.asyncio
async def test_policy_upload_creates_chunks_and_embeddings(
    client, admin_token, monkeypatch
):
    public_id = f"test-policy-{uuid.uuid4()}"
    destroyed: list[str] = []

    def fake_upload(*args, **kwargs):
        return {
            "public_id": public_id,
            "secure_url": "https://example.test/uploaded-policy.pdf",
        }

    def fake_destroy(uploaded_public_id, **kwargs):
        destroyed.append(uploaded_public_id)

    async def fake_embed(texts, title):
        assert title == "Leave Policy"
        return [
            [float(index + 1)] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
            for index, _ in enumerate(texts)
        ]

    async def fake_summary(title, category, texts):
        assert title == "Leave Policy"
        assert category == "leave"
        assert "Casual leave is 12 days." in texts
        return "Employees receive 12 days of casual leave."

    monkeypatch.setattr(policy_service.cloudinary.uploader, "upload", fake_upload)
    monkeypatch.setattr(policy_service.cloudinary.uploader, "destroy", fake_destroy)
    monkeypatch.setattr("app.rag.ingestion.embed_policy_texts", fake_embed)
    monkeypatch.setattr(policy_service, "generate_policy_summary", fake_summary)

    response = await client.post(
        "/api/v1/policies",
        data={"title": "Leave Policy", "category": "leave"},
        files={
            "file": (
                "leave.pdf",
                make_pdf(["Casual leave is 12 days."]),
                "application/pdf",
            )
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    document_id = uuid.UUID(response.json()["id"])

    monkeypatch.setattr(
        policies_api, "_download_policy_bytes", lambda _: b"%PDF-test-content"
    )
    download = await client.get(
        f"/api/v1/policies/{document_id}/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-test-content"
    assert download.headers["content-type"] == "application/pdf"
    assert "Leave%20Policy.pdf" in download.headers["content-disposition"]

    async with async_session() as db:
        rows = list(
            (
                await db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == document_id
                    )
                )
            ).all()
        )
        assert [(row.page_number, row.content) for row in rows] == [
            (1, "Casual leave is 12 days.")
        ]
        assert len(rows[0].embedding) == EMBEDDING_DIMENSIONS
        document = await db.get(PolicyDocument, document_id)
        assert document.summary == "Employees receive 12 days of casual leave."
        await db.delete(document)
        await db.commit()
    assert destroyed == []


@pytest.mark.asyncio
async def test_policy_upload_rolls_back_and_removes_file_when_embedding_fails(
    client, admin_token, monkeypatch
):
    title = f"Failed Policy {uuid.uuid4()}"
    destroyed: list[str] = []

    monkeypatch.setattr(
        policy_service.cloudinary.uploader,
        "upload",
        lambda *args, **kwargs: {
            "public_id": "failed-policy",
            "secure_url": "https://example.test/failed.pdf",
        },
    )
    monkeypatch.setattr(
        policy_service.cloudinary.uploader,
        "destroy",
        lambda public_id, **kwargs: destroyed.append(public_id),
    )

    async def fail_storage(*args, **kwargs):
        raise PolicyEmbeddingError("Gemini embedding failed. Please retry later.")

    async def fake_summary(*args, **kwargs):
        return "A grounded test policy summary."

    monkeypatch.setattr(
        policy_service,
        "generate_policy_summary",
        fake_summary,
    )
    monkeypatch.setattr(policy_service, "store_policy_chunks", fail_storage)
    response = await client.post(
        "/api/v1/policies",
        data={"title": title, "category": "leave"},
        files={"file": ("leave.pdf", make_pdf(["Policy text"]), "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 502
    assert destroyed == ["failed-policy"]
    async with async_session() as db:
        assert (
            await db.scalar(
                select(PolicyDocument.id).where(PolicyDocument.title == title)
            )
            is None
        )


@pytest.mark.asyncio
async def test_hr_and_admin_can_delete_policy_but_employee_cannot(
    client, admin_token, employee_token, monkeypatch
):
    hr_id = uuid.uuid4()
    hr_email = f"policy_hr_{uuid.uuid4().hex}@test.local"
    document_ids = [uuid.uuid4(), uuid.uuid4()]
    async with async_session() as db:
        hr = User(
            id=hr_id,
            email=hr_email,
            hashed_password=hash_password("PolicyPass!42"),
            role=RoleEnum.HR,
        )
        db.add(hr)
        await db.flush()
        for index, document_id in enumerate(document_ids):
            db.add(
                PolicyDocument(
                    id=document_id,
                    title=f"Deletable Policy {index}",
                    category="test",
                    file_path=(
                        "https://res.cloudinary.com/demo/raw/upload/v123/"
                        f"hrms/policies/delete-{index}"
                    ),
                    uploaded_by=hr_id,
                )
            )
        await db.flush()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=0,
                    page_number=1,
                    content="Indexed policy content",
                    embedding=[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
                )
                for document_id in document_ids
            ]
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": hr_email, "password": "PolicyPass!42"},
    )
    hr_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    employee_headers = {"Authorization": f"Bearer {employee_token}"}
    destroyed: list[str] = []
    monkeypatch.setattr(policy_service, "_ensure_configured", lambda: None)
    monkeypatch.setattr(
        policy_service.cloudinary.uploader,
        "destroy",
        lambda public_id, **kwargs: destroyed.append(public_id) or {"result": "ok"},
    )

    denied = await client.delete(
        f"/api/v1/policies/{document_ids[0]}", headers=employee_headers
    )
    assert denied.status_code == 403

    hr_deleted = await client.delete(
        f"/api/v1/policies/{document_ids[0]}", headers=hr_headers
    )
    admin_deleted = await client.delete(
        f"/api/v1/policies/{document_ids[1]}", headers=admin_headers
    )
    assert hr_deleted.status_code == 204, hr_deleted.text
    assert admin_deleted.status_code == 204, admin_deleted.text
    assert destroyed == [
        "hrms/policies/delete-0",
        "hrms/policies/delete-1",
    ]

    async with async_session() as db:
        assert await db.get(PolicyDocument, document_ids[0]) is None
        assert await db.get(PolicyDocument, document_ids[1]) is None
        chunks = list(
            (
                await db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id.in_(document_ids)
                    )
                )
            ).all()
        )
        assert chunks == []
        await db.execute(delete(User).where(User.id == hr_id))
        await db.commit()
