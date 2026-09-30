"""PDF extraction and page-aware text chunking for policy ingestion."""

import uuid
from dataclasses import dataclass
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.models.policy_document import PolicyDocument
from app.rag.embeddings import embed_policy_texts, validate_vectors


class PolicyExtractionError(ValueError):
    """A policy PDF cannot provide usable text for ingestion."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    page_number: int
    content: str


async def store_policy_chunks(
    db: AsyncSession, document_id: uuid.UUID, chunks: list[TextChunk]
) -> int:
    """Embed and replace chunks atomically within the caller's transaction.

    The caller must commit on success or roll back on failure. A savepoint
    preserves existing chunks if inserting a replacement fails. Upload wiring
    and permission checks belong to the policy service in Step 6.
    """
    if not chunks:
        raise ValueError("Cannot ingest an empty chunk list.")
    for index, chunk in enumerate(chunks):
        if (
            chunk.chunk_index != index
            or chunk.page_number < 1
            or not chunk.content.strip()
        ):
            raise ValueError(
                "Chunks must have consecutive indices, valid pages, and text."
            )
    document = await db.get(PolicyDocument, document_id)
    if document is None:
        raise ValueError("Policy document not found.")
    vectors = await embed_policy_texts(
        [chunk.content for chunk in chunks], document.title
    )
    validate_vectors(vectors, len(chunks))
    async with db.begin_nested():
        # Serialize replacement for this document, including concurrent retries.
        locked_id = await db.scalar(
            select(PolicyDocument.id)
            .where(PolicyDocument.id == document_id)
            .with_for_update()
        )
        if locked_id is None:
            raise ValueError("Policy document no longer exists.")
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        db.add_all(
            [
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    embedding=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
        )
        await db.flush()
    return len(chunks)


def chunk_pages(
    pages: list[ExtractedPage], *, chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[TextChunk]:
    """Split each page separately with a character limit and target overlap.

    Prefer paragraph, line, and word boundaries before splitting characters.
    Overlap may be smaller at natural boundaries and never crosses pages, so
    every chunk has an unambiguous source page. Indices span the whole document.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError(
            "chunk_overlap must be nonnegative and smaller than chunk_size"
        )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )
    chunks: list[TextChunk] = []
    for page in pages:
        if page.page_number < 1:
            raise ValueError("page_number must be positive")
        for text in splitter.split_text(page.text):
            if text.strip():
                chunks.append(TextChunk(len(chunks), page.page_number, text))
    return chunks


def extract_pdf_pages(contents: bytes) -> list[ExtractedPage]:
    """Extract nonempty pages, retaining their original one-based PDF numbers.

    This synchronous, CPU-bound helper should run in a worker thread when wired
    into the async upload endpoint. It does not perform OCR or external calls.
    Blank pages are skipped; scanned pages in mixed PDFs remain unsearchable.
    """
    if not contents:
        raise PolicyExtractionError("The uploaded PDF is empty.")
    if not contents.lstrip().startswith(b"%PDF-"):
        raise PolicyExtractionError("The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(BytesIO(contents))
        if reader.is_encrypted:
            raise PolicyExtractionError(
                "Password-protected PDFs are not supported. Upload an unencrypted copy."
            )

        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            raw_text = page.extract_text() or ""
            # Remove null bytes (PostgreSQL text cannot contain them), but keep
            # paragraph boundaries for the next step's text splitter.
            cleaned = (
                raw_text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
            )
            cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n")).strip()
            if cleaned:
                pages.append(ExtractedPage(page_number=page_number, text=cleaned))
    except PolicyExtractionError:
        raise
    except (PdfReadError, ValueError, TypeError, KeyError, IndexError) as exc:
        raise PolicyExtractionError(
            "The PDF could not be read. Upload a valid, undamaged PDF."
        ) from exc

    if not pages:
        raise PolicyExtractionError(
            "No readable text was found. Scanned or image-only PDFs need OCR first."
        )
    return pages
