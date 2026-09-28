import uuid

import pytest

from app.agent.nodes import query_rewriter as rewriter_module
from app.agent.nodes.query_rewriter import (
    correct_common_misspellings,
    query_rewriter_node,
)
from app.models.role import RoleEnum


def state(message: str, **extra) -> dict:
    return {
        "user_id": uuid.uuid4(),
        "role": RoleEnum.EMPLOYEE,
        "message": message,
        **extra,
    }


def test_policy_count_typoes_are_corrected_deterministically():
    assert (
        correct_common_misspellings("how many policie are ther")
        == "how many policies are there"
    )


def test_misspelled_announcement_action_is_normalized_safely():
    assert (
        correct_common_misspellings("i went to add annocenmte")
        == "I want to add announcement"
    )


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
async def test_announcement_action_example_does_not_call_llm(monkeypatch):
    async def must_not_run(message: str) -> str:
        raise AssertionError("Action requests must not be rewritten by the LLM")

    monkeypatch.setattr(rewriter_module, "rewrite_question", must_not_run)
    result = await query_rewriter_node(state("i went to add annocenmte"))

    assert result["message"] == "I want to add announcement"
    assert result["original_message"] == "i went to add annocenmte"


@pytest.mark.asyncio
async def test_unclear_non_action_message_can_be_reframed_by_llm(monkeypatch):
    async def fake_rewrite(message: str) -> str:
        assert message == "joining info please"
        return "What is my joining date?"

    monkeypatch.setattr(rewriter_module, "rewrite_question", fake_rewrite)
    result = await query_rewriter_node(state("joining info please"))

    assert result["message"] == "What is my joining date?"
    assert result["original_message"] == "joining info please"


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
