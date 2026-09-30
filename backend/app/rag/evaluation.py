"""Reproducible evaluation runner for the grounded policy RAG pipeline."""

import argparse
import asyncio
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session, engine
from app.rag.generation import UNKNOWN_ANSWER, GroundedAnswer, generate_grounded_answer
from app.rag.retrieval import RetrievedChunk, retrieve_policy_chunks

DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "evals" / "rag_questions.json"


class RagEvalCase(BaseModel):
    id: str
    question: str
    expects_answer: bool
    expected_pages: list[int] = Field(default_factory=list)
    evidence_terms: list[str] = Field(default_factory=list)
    answer_terms: list[str] = Field(default_factory=list)


class RagEvalResult(BaseModel):
    id: str
    passed: bool
    retrieval_passed: bool
    answer_passed: bool
    citations_passed: bool
    answer: str
    retrieved_pages: list[int]
    cited_pages: list[int]
    best_similarity: float | None


class RagEvalReport(BaseModel):
    passed: int
    total: int
    score: float
    target: int
    target_met: bool
    top_k: int
    max_cosine_distance: float
    results: list[RagEvalResult]


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", value.lower()).split())


def _contains_terms(value: str, terms: list[str]) -> bool:
    normalized = _normalize(value)
    return all(_normalize(term) in normalized for term in terms)


def _is_evidence(chunk: RetrievedChunk, case: RagEvalCase) -> bool:
    page_matches = not case.expected_pages or chunk.page_number in case.expected_pages
    return page_matches and _contains_terms(chunk.content, case.evidence_terms)


def score_rag_case(
    case: RagEvalCase,
    chunks: list[RetrievedChunk],
    generated: GroundedAnswer,
) -> RagEvalResult:
    cited_chunks = [
        chunks[number - 1]
        for number in generated.source_numbers
        if 1 <= number <= len(chunks)
    ]
    similarities = [chunk.similarity for chunk in chunks]

    if case.expects_answer:
        retrieval_passed = any(_is_evidence(chunk, case) for chunk in chunks)
        answer_passed = generated.answer != UNKNOWN_ANSWER and _contains_terms(
            generated.answer, case.answer_terms
        )
        citations_passed = any(_is_evidence(chunk, case) for chunk in cited_chunks)
    else:
        # Retrieval can return semantically adjacent text; the grounded generator
        # must still refuse when that context cannot support the requested fact.
        retrieval_passed = True
        answer_passed = generated.answer == UNKNOWN_ANSWER
        citations_passed = not generated.source_numbers

    return RagEvalResult(
        id=case.id,
        passed=retrieval_passed and answer_passed and citations_passed,
        retrieval_passed=retrieval_passed,
        answer_passed=answer_passed,
        citations_passed=citations_passed,
        answer=generated.answer,
        retrieved_pages=[chunk.page_number for chunk in chunks],
        cited_pages=[chunk.page_number for chunk in cited_chunks],
        best_similarity=max(similarities) if similarities else None,
    )


def load_eval_cases(path: Path = DEFAULT_DATASET) -> list[RagEvalCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    cases = [RagEvalCase.model_validate(case) for case in raw_cases]
    if len(cases) != 10:
        raise ValueError("The Day 16 RAG evaluation must contain exactly 10 cases.")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("RAG evaluation case IDs must be unique.")
    return cases


async def run_rag_evaluation(
    db: AsyncSession,
    cases: list[RagEvalCase],
    *,
    top_k: int | None = None,
    max_cosine_distance: float | None = None,
    target: int = 8,
) -> RagEvalReport:
    results = []
    for case in cases:
        chunks = await retrieve_policy_chunks(
            db,
            case.question,
            top_k=top_k,
            max_cosine_distance=max_cosine_distance,
        )
        generated = await generate_grounded_answer(case.question, chunks)
        results.append(score_rag_case(case, chunks, generated))

    passed = sum(result.passed for result in results)
    return RagEvalReport(
        passed=passed,
        total=len(results),
        score=passed / len(results) if results else 0,
        target=target,
        target_met=passed >= target,
        top_k=top_k if top_k is not None else settings.rag_top_k,
        max_cosine_distance=(
            max_cosine_distance
            if max_cosine_distance is not None
            else settings.rag_max_cosine_distance
        ),
        results=results,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the policy RAG pipeline")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--max-distance", type=float, default=None)
    parser.add_argument("--target", type=int, default=8)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    cases = load_eval_cases(args.dataset)
    # Keep evaluation output focused on case results rather than SQL statements.
    engine.echo = False
    async with async_session() as db:
        report = await run_rag_evaluation(
            db,
            cases,
            top_k=args.top_k,
            max_cosine_distance=args.max_distance,
            target=args.target,
        )
    if args.as_json:
        print(report.model_dump_json(indent=2))
    else:
        for result in report.results:
            marker = "PASS" if result.passed else "FAIL"
            print(
                f"[{marker}] {result.id}: retrieval={result.retrieval_passed} "
                f"answer={result.answer_passed} citations={result.citations_passed}"
            )
            print(f"  {result.answer}")
        print(
            f"\nScore: {report.passed}/{report.total} " f"(target {report.target}/10)"
        )
    return 0 if report.target_met else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
