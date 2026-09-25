import uuid

import pytest
from pydantic import SecretStr

from app.api.v1 import rag as rag_api
from app.db.session import async_session
from app.models.document_chunk import EMBEDDING_DIMENSIONS, DocumentChunk
from app.models.policy_document import PolicyDocument
from app.models.role import RoleEnum
from app.models.user import User
from app.rag import embeddings as embedding_module
from app.rag import retrieval as retrieval_module
from app.rag.generation import (
    UNKNOWN_ANSWER,
    GroundedAnswer,
    GroundedModelAnswer,
    generate_grounded_answer,
)
from app.rag.retrieval import RetrievedChunk, retrieve_policy_chunks


def vector(x: float, y: float = 0.0) -> list[float]:
    return [x, y] + [0.0] * (EMBEDDING_DIMENSIONS - 2)


def retrieved_chunk(index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        title="Leave Policy",
        category="leave",
        chunk_index=index,
        page_number=index + 1,
        content="Employees receive 12 casual leave days each year.",
        cosine_distance=0.1,
    )


@pytest.mark.asyncio
async def test_query_embedding_uses_question_answering_prefix(monkeypatch):
    calls: list[str] = []
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
            pass

        async def aembed_query(self, text):
            calls.append(text)
            return vector(1.0)

    monkeypatch.setattr(embedding_module, "GeminiPolicyEmbeddings", FakeEmbedder)
    monkeypatch.setattr(
        embedding_module.settings, "gemini_api_key", SecretStr("test-key")
    )

    result = await embedding_module.embed_policy_query("  How much leave?  ")

    assert len(result) == EMBEDDING_DIMENSIONS
    assert calls == ["task: question answering | query: How much leave?"]
    assert closed == {"async": True, "sync": True}


@pytest.mark.asyncio
async def test_retrieval_orders_by_similarity_and_applies_threshold(monkeypatch):
    monkeypatch.setattr(retrieval_module, "embed_policy_query", lambda question: None)

    async def fake_query_embedding(question):
        assert question == "What is my casual leave allowance?"
        return vector(1.0)

    monkeypatch.setattr(retrieval_module, "embed_policy_query", fake_query_embedding)

    async with async_session() as db:
        user = User(
            id=uuid.uuid4(),
            email=f"retrieval_{uuid.uuid4().hex}@test.local",
            hashed_password="unused",
            role=RoleEnum.ADMIN,
        )
        db.add(user)
        await db.flush()
        document = PolicyDocument(
            id=uuid.uuid4(),
            title="Leave Policy",
            category="leave",
            file_path="https://example.test/leave.pdf",
            uploaded_by=user.id,
        )
        db.add(document)
        await db.flush()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=1,
                    content="Exact casual leave policy",
                    embedding=vector(1.0),
                ),
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=1,
                    page_number=2,
                    content="Related leave policy",
                    embedding=vector(0.8, 0.6),
                ),
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=2,
                    page_number=3,
                    content="Opposite and irrelevant",
                    embedding=vector(-1.0),
                ),
            ]
        )
        await db.flush()

        results = await retrieve_policy_chunks(
            db,
            "What is my casual leave allowance?",
            top_k=5,
            max_cosine_distance=0.5,
        )

        assert [item.chunk_index for item in results] == [0, 1]
        assert results[0].similarity == pytest.approx(1.0)
        assert results[1].similarity == pytest.approx(0.8)
        await db.rollback()


@pytest.mark.asyncio
async def test_generation_returns_only_valid_cited_sources(monkeypatch):
    class FakeChain:
        async def ainvoke(self, values):
            assert "[Source 1] Leave Policy" in values["context"]
            return GroundedModelAnswer(
                supported=True,
                answer="Employees receive 12 casual leave days each year.",
                source_numbers=[2, 1, 2, 99],
            )

    monkeypatch.setattr("app.rag.generation.build_grounded_chain", lambda: FakeChain())
    result = await generate_grounded_answer(
        "How much casual leave do I receive?",
        [retrieved_chunk(0), retrieved_chunk(1)],
    )

    assert result.answer.startswith("Employees receive 12")
    assert result.source_numbers == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_result",
    [
        GroundedModelAnswer(supported=False, answer="Unsupported", source_numbers=[]),
        GroundedModelAnswer(
            supported=True, answer="Claim without evidence", source_numbers=[99]
        ),
    ],
)
async def test_generation_falls_back_when_unsupported_or_uncited(
    monkeypatch, model_result
):
    class FakeChain:
        async def ainvoke(self, values):
            return model_result

    monkeypatch.setattr("app.rag.generation.build_grounded_chain", lambda: FakeChain())
    result = await generate_grounded_answer("Unknown question", [retrieved_chunk()])

    assert result.answer == UNKNOWN_ANSWER
    assert result.source_numbers == []


@pytest.mark.asyncio
async def test_generation_skips_model_when_retrieval_is_empty(monkeypatch):
    monkeypatch.setattr(
        "app.rag.generation.build_grounded_chain",
        lambda: pytest.fail("Model must not be called without context"),
    )
    result = await generate_grounded_answer("Unknown question", [])
    assert result.answer == UNKNOWN_ANSWER


@pytest.mark.asyncio
async def test_ask_endpoint_requires_login(client):
    response = await client.post("/api/v1/rag/ask", json={"question": "Leave?"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ask_endpoint_returns_answer_and_source(
    client, employee_token, monkeypatch
):
    chunk = retrieved_chunk()

    async def fake_retrieve(db, question, *, top_k=None):
        assert question == "How much casual leave?"
        assert top_k == 3
        return [chunk]

    async def fake_generate(question, chunks):
        return GroundedAnswer(answer="12 days.", source_numbers=[1])

    monkeypatch.setattr(rag_api, "retrieve_policy_chunks", fake_retrieve)
    monkeypatch.setattr(rag_api, "generate_grounded_answer", fake_generate)

    response = await client.post(
        "/api/v1/rag/ask",
        json={"question": "How much casual leave?", "top_k": 3},
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "12 days."
    assert body["sources"][0]["document_id"] == str(chunk.document_id)
    assert body["sources"][0]["page_number"] == 1
    assert body["sources"][0]["similarity"] == 0.9
