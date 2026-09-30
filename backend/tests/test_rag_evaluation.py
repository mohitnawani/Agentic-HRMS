import json
import uuid

import pytest

from app.rag.evaluation import RagEvalCase, load_eval_cases, score_rag_case
from app.rag.generation import UNKNOWN_ANSWER, GroundedAnswer
from app.rag.retrieval import RetrievedChunk


def chunk(*, page: int, content: str, distance: float = 0.1) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        title="Policy",
        category="hr",
        chunk_index=0,
        page_number=page,
        content=content,
        cosine_distance=distance,
    )


def supported_case() -> RagEvalCase:
    return RagEvalCase(
        id="roles",
        question="Which roles are supported?",
        expects_answer=True,
        expected_pages=[1],
        evidence_terms=["admin", "hr", "employee"],
        answer_terms=["admin", "hr", "employee"],
    )


def test_supported_case_requires_retrieval_answer_and_evidence_citation():
    chunks = [chunk(page=1, content="The roles are Admin, HR, and Employee.")]
    result = score_rag_case(
        supported_case(),
        chunks,
        GroundedAnswer(
            answer="Admin, HR, and Employee are supported.", source_numbers=[1]
        ),
    )
    assert result.passed
    assert result.cited_pages == [1]
    assert result.best_similarity == pytest.approx(0.9)


@pytest.mark.parametrize(
    "chunks,answer",
    [
        (
            [chunk(page=2, content="The roles are Admin, HR, and Employee.")],
            GroundedAnswer(
                answer="Admin, HR, and Employee are supported.", source_numbers=[1]
            ),
        ),
        (
            [chunk(page=1, content="The roles are Admin, HR, and Employee.")],
            GroundedAnswer(answer="Only Admin is supported.", source_numbers=[1]),
        ),
        (
            [
                chunk(page=1, content="The roles are Admin, HR, and Employee."),
                chunk(page=2, content="Unrelated text."),
            ],
            GroundedAnswer(
                answer="Admin, HR, and Employee are supported.", source_numbers=[2]
            ),
        ),
    ],
)
def test_supported_case_fails_when_any_grounding_dimension_fails(chunks, answer):
    assert not score_rag_case(supported_case(), chunks, answer).passed


def test_unsupported_case_requires_exact_fallback_without_citations():
    case = RagEvalCase(
        id="unknown",
        question="What is the cafeteria menu?",
        expects_answer=False,
    )
    chunks = [chunk(page=3, content="Employee benefits overview")]

    passing = score_rag_case(case, chunks, GroundedAnswer(answer=UNKNOWN_ANSWER))
    cited = score_rag_case(
        case,
        chunks,
        GroundedAnswer(answer=UNKNOWN_ANSWER, source_numbers=[1]),
    )

    assert passing.passed
    assert not cited.passed


def test_dataset_must_have_exactly_ten_unique_cases(tmp_path):
    path = tmp_path / "cases.json"
    case = {
        "id": "duplicate",
        "question": "Question?",
        "expects_answer": False,
    }
    path.write_text(json.dumps([case] * 10), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        load_eval_cases(path)


def test_repository_dataset_is_valid():
    cases = load_eval_cases()
    assert len(cases) == 10
    assert sum(case.expects_answer for case in cases) == 8
