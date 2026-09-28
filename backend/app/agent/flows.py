"""Deterministic workflow policy for agent actions.

The model may identify an intent and extract values, but this module remains
the source of truth for permissions, slot order, and confirmation behavior.
"""

from dataclasses import dataclass
from typing import Literal

WorkflowIntent = Literal[
    "CREATE_EMPLOYEE",
    "UPDATE_EMPLOYEE",
    "DELETE_EMPLOYEE",
    "APPROVE_LEAVE",
    "REJECT_LEAVE",
    "CREATE_DEPARTMENT",
    "CREATE_ANNOUNCEMENT",
    "UPLOAD_POLICY",
    "DELETE_POLICY",
    "APPLY_LEAVE",
    "CANCEL_LEAVE",
    "CHECK_IN",
    "CHECK_OUT",
]


@dataclass(frozen=True)
class WorkflowSpec:
    tool: str
    permission: str
    required_slots: tuple[str, ...]
    confirmation: Literal["none", "standard", "strong"] = "standard"


WORKFLOWS: dict[WorkflowIntent, WorkflowSpec] = {
    "CREATE_EMPLOYEE": WorkflowSpec(
        "create_employee",
        "employee:create",
        ("first_name", "last_name", "email", "date_of_joining"),
    ),
    "UPDATE_EMPLOYEE": WorkflowSpec(
        "update_employee", "employee:update", ("employee_id", "updates")
    ),
    "DELETE_EMPLOYEE": WorkflowSpec(
        "delete_employee", "employee:delete", ("employee_id",), "strong"
    ),
    "APPROVE_LEAVE": WorkflowSpec(
        "approve_leave", "leave:approve", ("request_id",)
    ),
    "REJECT_LEAVE": WorkflowSpec(
        "reject_leave", "leave:approve", ("request_id",)
    ),
    "CREATE_DEPARTMENT": WorkflowSpec(
        "create_department", "department:write", ("name",)
    ),
    "CREATE_ANNOUNCEMENT": WorkflowSpec(
        "create_announcement", "announcement:write", ("title", "body")
    ),
    "UPLOAD_POLICY": WorkflowSpec(
        "upload_policy",
        "policy:write",
        ("title", "category", "policy_file", "document_id"),
    ),
    "DELETE_POLICY": WorkflowSpec(
        "delete_policy", "policy:write", ("document_id",), "strong"
    ),
    "APPLY_LEAVE": WorkflowSpec(
        "apply_leave",
        "leave:apply",
        ("leave_type_id", "start_date", "end_date", "reason"),
    ),
    "CANCEL_LEAVE": WorkflowSpec(
        "cancel_leave", "leave:apply", ("request_id",)
    ),
    "CHECK_IN": WorkflowSpec(
        "check_in", "attendance:check_in_out", (), "none"
    ),
    "CHECK_OUT": WorkflowSpec(
        "check_out", "attendance:check_in_out", (), "none"
    ),
}

TOOL_WORKFLOWS = {spec.tool: spec for spec in WORKFLOWS.values()}


def missing_slots(tool: str, collected: dict[str, object]) -> list[str]:
    spec = TOOL_WORKFLOWS[tool]
    if tool == "delete_employee" and collected.get("bulk"):
        return []
    return [
        slot
        for slot in spec.required_slots
        if collected.get(slot) in (None, "")
        or (slot == "updates" and not collected.get(slot))
    ]
