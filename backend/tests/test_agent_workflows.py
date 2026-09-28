from datetime import UTC, datetime, timedelta

from app.agent.flows import TOOL_WORKFLOWS, missing_slots
from app.agent.nodes.action_agent import (
    CANCELLATION_WORDS,
    CONFIRMATION_WORDS,
    _extract_initial_payload,
    _pending_expired,
)
from app.agent.supervisor import supervisor_node
from app.models.role import RoleEnum


def test_every_supported_write_uses_confirmation_except_attendance() -> None:
    immediate = {
        tool for tool, spec in TOOL_WORKFLOWS.items() if spec.confirmation == "none"
    }
    assert immediate == {"check_in", "check_out"}


def test_create_employee_never_collects_a_password_from_chat() -> None:
    assert missing_slots("create_employee", {}) == [
        "first_name",
        "last_name",
        "email",
        "date_of_joining",
    ]
    assert "password" not in TOOL_WORKFLOWS["create_employee"].required_slots


def test_missing_slots_are_deterministic_and_ordered() -> None:
    assert missing_slots(
        "apply_leave",
        {"leave_type_id": "type", "start_date": "2026-10-05"},
    ) == ["end_date", "reason"]


def test_only_explicit_confirmation_words_are_accepted() -> None:
    assert {"yes", "confirm", "haan kar do", "do it"} <= CONFIRMATION_WORDS
    assert "maybe" not in CONFIRMATION_WORDS
    assert "yes but change the date" not in CONFIRMATION_WORDS
    assert {"cancel", "never mind", "nahi", "rehne do"} <= CANCELLATION_WORDS


def test_pending_workflow_expires_by_time_or_turn_count() -> None:
    old = (datetime.now(UTC) - timedelta(minutes=11)).isoformat()
    assert _pending_expired({"started_at": old, "turns": 0})
    assert _pending_expired({"started_at": datetime.now(UTC).isoformat(), "turns": 6})
    assert not _pending_expired(
        {"started_at": datetime.now(UTC).isoformat(), "turns": 2}
    )


def test_employee_name_is_extracted_but_never_assumed_to_be_an_id() -> None:
    payload = _extract_initial_payload(
        "delete_employee",
        {
            "user_id": "00000000-0000-4000-8000-000000000001",
            "role": RoleEnum.ADMIN,
            "message": "delete employee Rahul Kumar",
        },
    )
    assert payload == {"employee_name": "Rahul Kumar"}

    short_payload = _extract_initial_payload(
        "delete_employee",
        {
            "user_id": "00000000-0000-4000-8000-000000000001",
            "role": RoleEnum.ADMIN,
            "message": "i want to remove manjeet",
        },
    )
    assert short_payload == {"employee_name": "manjeet"}


def test_read_question_interrupts_without_replacing_pending_write() -> None:
    state = {
        "user_id": "00000000-0000-4000-8000-000000000001",
        "role": RoleEnum.EMPLOYEE,
        "message": "what is my leave balance?",
        "pending_action": {
            "tool": "apply_leave",
            "stage": "slots",
            "missing_field": "end_date",
        },
    }
    assert supervisor_node(state)["intent"] == "database"


def test_non_read_message_resumes_pending_write() -> None:
    state = {
        "user_id": "00000000-0000-4000-8000-000000000001",
        "role": RoleEnum.EMPLOYEE,
        "message": "2026-10-07",
        "pending_action": {
            "tool": "apply_leave",
            "stage": "slots",
            "missing_field": "end_date",
        },
    }
    assert supervisor_node(state)["intent"] == "action"
