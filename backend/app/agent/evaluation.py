"""Deterministic Day 20 intent-routing evaluation."""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from app.agent.state import AgentIntent
from app.agent.supervisor import classify_intent

DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "evals" / "agent_intents.json"


class IntentEvalCase(BaseModel):
    id: str
    prompt: str
    expected_intent: AgentIntent


class IntentEvalResult(BaseModel):
    id: str
    prompt: str
    expected_intent: AgentIntent
    actual_intent: AgentIntent
    passed: bool


class IntentEvalReport(BaseModel):
    passed: int
    total: int
    score: float
    target: int
    target_met: bool
    results: list[IntentEvalResult]


def load_intent_cases(path: Path = DEFAULT_DATASET) -> list[IntentEvalCase]:
    cases = [
        IntentEvalCase.model_validate(item)
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]
    if len(cases) != 10:
        raise ValueError("The Day 20 intent evaluation must contain exactly 10 cases.")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Intent evaluation case IDs must be unique.")
    return cases


def run_intent_evaluation(
    cases: list[IntentEvalCase], *, target: int = 8
) -> IntentEvalReport:
    results = []
    for case in cases:
        actual = classify_intent(case.prompt)
        results.append(
            IntentEvalResult(
                id=case.id,
                prompt=case.prompt,
                expected_intent=case.expected_intent,
                actual_intent=actual,
                passed=actual == case.expected_intent,
            )
        )
    passed = sum(result.passed for result in results)
    return IntentEvalReport(
        passed=passed,
        total=len(results),
        score=passed / len(results) if results else 0,
        target=target,
        target_met=passed >= target,
        results=results,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate agent intent routing")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--target", type=int, default=8)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_intent_evaluation(load_intent_cases(args.dataset), target=args.target)
    if args.as_json:
        print(report.model_dump_json(indent=2))
    else:
        for result in report.results:
            marker = "PASS" if result.passed else "FAIL"
            print(
                f"[{marker}] {result.id}: expected={result.expected_intent} "
                f"actual={result.actual_intent}"
            )
        print(f"\nScore: {report.passed}/{report.total} (target {report.target}/10)")
    return 0 if report.target_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
