from datetime import UTC, datetime, timedelta

from app.agent.flows import TOOL_WORKFLOWS, missing_slots
from app.agent.nodes.action_agent import (
    CANCELLATION_WORDS,
    CONFIRMATION_WORDS,
    _extract_initial_payload,
    _pending_expired,
    select_action_tool,
)
from app.agent.nodes.database_agent import select_database_tool
from app.agent.nodes.query_rewriter import correct_common_misspellings
from app.agent.supervisor import classify_intent, supervisor_node
from app.models.role import RoleEnum


def test_every_supported_write_uses_confirmation_except_attendance() -> None:
    immediate = {
        tool for tool, spec in TOOL_WORKFLOWS.items() if spec.confirmation == "none"
    }
    assert immediate == {"check_in", "check_out", "upload_employee_photo"}


def test_create_employee_never_collects_a_password_from_chat() -> None:
    assert missing_slots("create_employee", {}) == [
        "first_name",
        "last_name",
        "email",
        "date_of_joining",
        "role",
    ]
    assert "password" not in TOOL_WORKFLOWS["create_employee"].required_slots


def test_missing_slots_are_deterministic_and_ordered() -> None:
    assert missing_slots(
        "apply_leave",
        {"leave_type_id": "type", "start_date": "2026-10-05"},
    ) == ["end_date", "reason"]

    assert missing_slots("correct_attendance", {}) == [
        "employee_id",
        "date",
        "status",
        "correction_reason",
    ]


def test_attendance_correction_is_recognized_with_common_typo() -> None:
    corrected = correct_common_misspellings("correct attence")
    assert corrected == "correct attendance"
    assert select_action_tool(corrected) == "correct_attendance"


def test_admin_management_commands_select_the_expected_tools() -> None:
    commands = {
        "add department Finance": "create_department",
        "remove department": "delete_department",
        "add designation Manager": "create_designation",
        "delete designation": "delete_designation",
        "add announcement": "create_announcement",
        "remove announcement": "delete_announcement",
        "create holiday Diwali": "create_holiday",
        "delete holiday": "delete_holiday",
        "add policy": "upload_policy",
        "edit policy": "update_policy",
        "remove policy": "delete_policy",
        "approve leave": "approve_leave",
        "reject leave": "reject_leave",
        "create leave type": "create_leave_type",
    }
    for command, expected in commands.items():
        assert select_action_tool(command) == expected


def test_flexible_hr_leave_approval_phrases() -> None:
    approve_phrases = (
        "approve",
        "approve task",
        "approve leave",
        "accept Rahul's leave request",
        "grant leave approval",
    )
    reject_phrases = (
        "reject",
        "reject task",
        "decline Rahul's leave",
        "deny leave request",
    )
    for message in approve_phrases:
        assert classify_intent(message) == "action"
        assert select_action_tool(message) == "approve_leave"
    for message in reject_phrases:
        assert classify_intent(message) == "action"
        assert select_action_tool(message) == "reject_leave"


def test_admin_read_commands_select_management_lists() -> None:
    assert select_database_tool("how many holidays are there") == "get_holidays"
    assert select_database_tool("show pending leaves") == "list_pending_leave_requests"
    assert select_database_tool("show me the leave approvals") == "list_pending_leave_requests"
    assert select_database_tool("show employee leaves") == "list_pending_leave_requests"
    assert select_database_tool("show HR pending leaves") == "list_pending_leave_requests"
    assert select_database_tool("show me approvals") == "list_pending_leave_requests"
    assert select_database_tool("see leave requests") == "list_leave_requests"
    assert select_database_tool("show leaves") == "list_leave_requests"
    assert select_database_tool("show approved leaves") == "list_leave_requests"
    assert select_database_tool("show rejected leaves") == "list_leave_requests"
    assert select_database_tool("show my leaves") == "get_leave_history"
    assert select_database_tool("manage leave requests") == "list_pending_leave_requests"
    assert select_database_tool("show departments") == "list_departments"
    assert select_database_tool("show designations") == "list_designations"
    assert select_database_tool("show users") == "list_users"
    assert select_database_tool("show employee") == "list_employees"
    assert select_database_tool("show employee Rahul Kumar") == "get_employee_details"
    assert select_database_tool("get employee EMP-004 details") == "get_employee_details"
    assert select_database_tool("find employee rahul@example.com") == "get_employee_details"
    assert select_database_tool("tell me about employee Rahul") == "get_employee_details"
    assert select_database_tool("show Rahul details") == "get_employee_details"
    assert select_database_tool("show details for EMP-004") == "get_employee_details"
    assert select_database_tool("show leave details") != "get_employee_details"


def test_admin_command_typos_are_normalized_before_routing() -> None:
    assert correct_common_misspellings("reomve policky") == "remove policy"
    assert correct_common_misspellings("add anoucmetn") == "add announcement"
    assert correct_common_misspellings("rejdct leave") == "reject leave"
    assert correct_common_misspellings("apporve task") == "approve task"
    assert correct_common_misspellings("show apprvsl") == "show approvals"


def test_only_explicit_confirmation_words_are_accepted() -> None:
    assert {"yes", "confirm", "haan kar do", "do it"} <= CONFIRMATION_WORDS
    assert "maybe" not in CONFIRMATION_WORDS
    assert "yes but change the date" not in CONFIRMATION_WORDS
    assert {"cancel", "exit", "exit flow", "quit", "never mind", "nahi", "rehne do"} <= CANCELLATION_WORDS


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


def test_read_question_cannot_interrupt_pending_write() -> None:
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
    assert supervisor_node(state)["intent"] == "action"


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


def test_domain_word_is_used_as_pending_value_not_a_new_read_request() -> None:
    base_state = {
        "user_id": "00000000-0000-4000-8000-000000000001",
        "role": RoleEnum.HR,
        "pending_action": {
            "tool": "create_announcement",
            "stage": "slots",
            "missing_field": "title",
        },
    }
    assert supervisor_node({**base_state, "message": "Holiday"})["intent"] == "action"
    assert supervisor_node({**base_state, "message": "Leave policy"})["intent"] == "action"
    assert supervisor_node({**base_state, "message": "Show all holidays"})["intent"] == "action"
