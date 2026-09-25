"""Gemini Embedding 2 adapter for LangChain's document embedding interface."""

import math

from google.genai.types import EmbedContentConfig, HttpOptions, HttpRetryOptions
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.models.document_chunk import EMBEDDING_DIMENSIONS


class PolicyEmbeddingError(ValueError):
    """Embedding configuration, provider, or output validation failed."""


class GeminiPolicyEmbeddings(GoogleGenerativeAIEmbeddings):
    def _build_config(self, *, task_type=None, title=None, output_dimensionality=None):
        # Embedding 2 uses text prefixes, not the wrapper's legacy task_type.
        return EmbedContentConfig(
            output_dimensionality=output_dimensionality,
            http_options=HttpOptions(
                timeout=int(settings.embedding_timeout_seconds * 1000),
                retry_options=HttpRetryOptions(
                    attempts=settings.embedding_max_retries + 1
                ),
            ),
        )


def validate_vectors(vectors: list[list[float]], expected_count: int) -> None:
    if len(vectors) != expected_count:
        raise PolicyEmbeddingError("Embedding count does not match chunk count.")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise PolicyEmbeddingError(
                "Embedding dimensions do not match the database."
            )
        if not all(math.isfinite(value) and abs(value) <= 3.4e38 for value in vector):
            raise PolicyEmbeddingError("Embedding contains invalid numeric values.")
        if not any(vector):
            raise PolicyEmbeddingError("Embedding cannot be a zero vector.")


def _create_embedder() -> GeminiPolicyEmbeddings:
    if (
        not settings.gemini_api_key
        or not settings.gemini_api_key.get_secret_value().strip()
    ):
        raise PolicyEmbeddingError(
            "Set GEMINI_API_KEY in the root .env to enable ingestion."
        )
    return GeminiPolicyEmbeddings(
        model=settings.embedding_model,
        api_key=settings.gemini_api_key,
        vertexai=False,
        output_dimensionality=settings.embedding_dimensions,
    )


async def _close_embedder(embedder: GeminiPolicyEmbeddings) -> None:
    await embedder.client.aio.aclose()
    embedder.client.close()


async def embed_policy_texts(texts: list[str], title: str) -> list[list[float]]:
    if not texts:
        return []
    embedder = _create_embedder()
    vectors = []
    try:
        # Small sequential batches limit request size and concurrent quota use.
        for start in range(0, len(texts), 16):
            batch = texts[start : start + 16]
            prepared = [f"title: {title or 'none'} | text: {text}" for text in batch]
            result = await embedder.aembed_documents(prepared, batch_size=16)
            validate_vectors(result, len(batch))
            vectors.extend(result)
    except PolicyEmbeddingError:
        raise
    except Exception as exc:
        # Provider errors can include request data; expose only a safe message.
        raise PolicyEmbeddingError(
            "Gemini embedding failed. Please retry later."
        ) from exc
    finally:
        await _close_embedder(embedder)
    return vectors


async def embed_policy_query(question: str) -> list[float]:
    """Embed a user question in the same vector space as policy chunks."""
    normalized = " ".join(question.split())
    if not normalized:
        raise PolicyEmbeddingError("Question cannot be empty.")
    embedder = _create_embedder()
    try:
        # Gemini Embedding 2 uses natural-language prefixes for retrieval intent.
        vector = await embedder.aembed_query(
            f"task: question answering | query: {normalized}"
        )
        validate_vectors([vector], 1)
        return vector
    except PolicyEmbeddingError:
        raise
    except Exception as exc:
        raise PolicyEmbeddingError(
            "Gemini embedding failed. Please retry later."
        ) from exc
    finally:
        await _close_embedder(embedder)
