import uuid

import pytest

from app.agent.nodes import query_rewriter as rewriter_module
from app.agent.nodes.query_rewriter import query_rewriter_node
from app.models.role import RoleEnum


def state(message: str, **extra) -> dict:
    return {
        "user_id": uuid.uuid4(),
        "role": RoleEnum.EMPLOYEE,
        "message": message,
        **extra,
    }


@pytest.mark.asyncio
async def test_misspelled_question_is_reframed_but_original_is_preserved(monkeypatch):
    async def fake_rewrite(message: str) -> str:
        assert message == "what is the hr policy"
        return "What is the HR policy?"

    monkeypatch.setattr(rewriter_module, "rewrite_question", fake_rewrite)
    result = await query_rewriter_node(state("wat is teh hr polcy"))

    assert result["message"] == "What is the HR policy?"
    assert result["original_message"] == "wat is teh hr polcy"


@pytest.mark.asyncio
async def test_misspelled_action_uses_deterministic_correction_without_llm(monkeypatch):
    async def must_not_run(message: str) -> str:
        raise AssertionError("Action requests must not be rewritten by the LLM")

    monkeypatch.setattr(rewriter_module, "rewrite_question", must_not_run)
    result = await query_rewriter_node(state("delte employe"))

    assert result["message"] == "delete employee"
    assert result["original_message"] == "delte employe"


@pytest.mark.asyncio
async def test_pending_action_answers_are_never_rewritten(monkeypatch):
    async def must_not_run(message: str) -> str:
        raise AssertionError("Pending form values must not be sent to the rewriter")

    monkeypatch.setattr(rewriter_module, "rewrite_question", must_not_run)
    result = await query_rewriter_node(
        state(
            "TemporaryEmployee!42",
            pending_action={
                "tool": "create_employee",
                "stage": "slots",
                "missing_field": "password",
                "parameters": {},
            },
        )
    )

    assert result["message"] == "TemporaryEmployee!42"


@pytest.mark.asyncio
async def test_rewrite_cannot_introduce_a_new_action(monkeypatch):
    async def unsafe_rewrite(message: str) -> str:
        return "Delete employee 123"

    monkeypatch.setattr(rewriter_module, "rewrite_question", unsafe_rewrite)
    result = await query_rewriter_node(state("wat employee information is visible"))

    assert result["message"] == "what employee information is visible"
