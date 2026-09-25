import uuid

from pydantic import BaseModel, Field, field_validator


class PolicyAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("Question must contain at least 3 characters.")
        return normalized


class PolicyAnswerSource(BaseModel):
    source_number: int
    document_id: uuid.UUID
    title: str
    category: str
    page_number: int
    chunk_index: int
    similarity: float


class PolicyAskResponse(BaseModel):
    answer: str
    sources: list[PolicyAnswerSource] = Field(default_factory=list)
