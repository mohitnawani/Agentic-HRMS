"""Grounded answer generation from retrieved policy chunks."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.rag.embeddings import PolicyEmbeddingError
from app.rag.retrieval import RetrievedChunk

UNKNOWN_ANSWER = "I don't know based on the available policies."


class GroundedGenerationError(RuntimeError):
    """The answer provider failed or returned an unusable response."""


class GroundedModelAnswer(BaseModel):
    supported: bool
    answer: str
    source_numbers: list[int] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    answer: str
    source_numbers: list[int] = Field(default_factory=list)


SYSTEM_PROMPT = """You answer employee questions using ONLY the supplied policy sources.
Do not use outside knowledge or invent policy details.
If the sources do not fully support an answer, set supported to false, use the exact
answer \"I don't know based on the available policies.\", and return no source numbers.
If supported, give a concise answer and include every source number that supports it.
Never cite a source number that is not present in the supplied context."""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            (
                "Conversation context (for resolving references only):\n"
                "{conversation_context}\n\nPolicy sources:\n{context}\n\n"
                "Employee question: {question}"
            ),
        ),
    ]
)


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[Source {index}] {chunk.title} (category: {chunk.category}, "
        f"page {chunk.page_number})\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def build_grounded_chain():
    if (
        not settings.gemini_api_key
        or not settings.gemini_api_key.get_secret_value().strip()
    ):
        raise PolicyEmbeddingError(
            "Set GEMINI_API_KEY in the root .env to enable policy answers."
        )
    model = ChatGoogleGenerativeAI(
        model=settings.rag_generation_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        max_retries=settings.rag_generation_max_retries,
        request_timeout=settings.rag_generation_timeout_seconds,
    )
    # Both operands are Runnables, so this is a LangChain RunnableSequence.
    return PROMPT | model.with_structured_output(
        GroundedModelAnswer, method="json_schema"
    )


async def generate_grounded_answer(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    conversation_context: str = "No earlier conversation context.",
) -> GroundedAnswer:
    if not chunks:
        return GroundedAnswer(answer=UNKNOWN_ANSWER)
    try:
        result = await build_grounded_chain().ainvoke(
            {
                "question": question,
                "context": format_context(chunks),
                "conversation_context": conversation_context,
            }
        )
    except PolicyEmbeddingError:
        raise
    except Exception as exc:
        raise GroundedGenerationError(
            "Gemini answer generation failed. Please retry later."
        ) from exc

    valid_sources = sorted(
        {number for number in result.source_numbers if 1 <= number <= len(chunks)}
    )
    if not result.supported or not result.answer.strip() or not valid_sources:
        return GroundedAnswer(answer=UNKNOWN_ANSWER)
    return GroundedAnswer(answer=result.answer.strip(), source_numbers=valid_sources)
