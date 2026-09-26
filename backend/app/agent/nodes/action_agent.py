"""Permission-controlled actions with slot filling and confirmation gates."""

import re
import uuid
from typing import Literal, cast

from fastapi import HTTPException
from langgraph.runtime import Runtime
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.agent.state import AgentRuntimeContext, AgentState, AgentToolResult
from app.agent.tools.write_tools import (
    WriteToolAccessDenied,
    WriteToolConflict,
    apply_leave,
    approve_leave,
    authorize_write_tool,
    cancel_leave,
    complete_policy_upload,
    create_announcement,
    create_department,
    create_employee,
    delete_employee,
    delete_policy,
    record_attendance_action,
    reject_leave,
    update_employee,
)
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate
from app.schemas.common import EmailT
from app.schemas.department import DepartmentCreate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.schemas.leave import LeaveRequestCreate

ActionToolName = Literal[
    "create_employee",
    "update_employee",
    "delete_employee",
    "approve_leave",
    "reject_leave",
    "create_department",
    "create_announcement",
    "upload_policy",
    "delete_policy",
    "apply_leave",
    "cancel_leave",
    "check_in",
    "check_out",
]

UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
EMAIL_ADAPTER = TypeAdapter(EmailT)
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CONFIRMATION_WORDS = {"yes", "y", "confirm", "confirmed", "proceed"}
CANCELLATION_WORDS = {"no", "n", "cancel", "stop", "abort"}
SENSITIVE_ACTIONS = {
    "delete_employee",
    "approve_leave",
    "reject_leave",
    "create_announcement",
    "apply_leave",
    "cancel_leave",
    "delete_policy",
}

REQUIRED_FIELDS: dict[ActionToolName, tuple[str, ...]] = {
    "create_employee": (
        "first_name",
        "last_name",
        "email",
        "date_of_joining",
        "password",
    ),
    "update_employee": ("employee_id", "updates"),
    "delete_employee": ("employee_id",),
    "approve_leave": ("request_id",),
    "reject_leave": ("request_id",),
    "create_department": ("name",),
    "create_announcement": ("title", "body"),
    "upload_policy": ("title", "category", "policy_file", "document_id"),
    "delete_policy": ("document_id",),
    "apply_leave": ("leave_type_id", "start_date", "end_date", "reason"),
    "cancel_leave": ("request_id",),
    "check_in": (),
    "check_out": (),
}

FIELD_PROMPTS = {
    "first_name": "What is the employee's first name?",
    "last_name": "What is the employee's last name?",
    "email": "What is the employee's email address?",
    "date_of_joining": "What is the joining date? Please use YYYY-MM-DD.",
    "password": "Enter a temporary password for the employee.",
    "employee_id": "What is the employee ID?",
    "request_id": "What is the leave request ID?",
    "updates": "Which employee fields should be updated?",
    "name": "What is the department name?",
    "title": "What title should be used?",
    "body": "What should the announcement say?",
    "category": "What category should this policy use?",
    "policy_file": "Choose the PDF policy file to upload.",
    "document_id": "Which policy document should be deleted?",
    "leave_type_id": "Which leave type would you like to use?",
    "start_date": "What is the leave start date? Please use YYYY-MM-DD.",
    "end_date": "What is the leave end date? Please use YYYY-MM-DD.",
    "reason": "What is the reason for your leave?",
}


def select_action_tool(message: str) -> ActionToolName | None:
    normalized = " ".join(message.lower().split())
    patterns: tuple[tuple[str, ActionToolName], ...] = (
        (r"\b(create|add)\b.*\b(employees?|users?)\b", "create_employee"),
        (r"\b(update|change|edit)\b.*\b(employees?|users?)\b", "update_employee"),
        (r"\b(delete|remove)\b.*\b(employees?|users?)\b", "delete_employee"),
        (r"\b(delete|remove)\b.*\b(policies|policy|documents?)\b", "delete_policy"),
        (r"\bapprove\b.*\bleave\b", "approve_leave"),
        (r"\breject\b.*\bleave\b", "reject_leave"),
        (r"\bapply\b.*\bleave\b", "apply_leave"),
        (r"\bcancel\b.*\bleave\b", "cancel_leave"),
        (r"\bcheck[ -]?in\b", "check_in"),
        (r"\bcheck[ -]?out\b", "check_out"),
        (r"\b(create|add)\b.*\bdepartments?\b", "create_department"),
        (
            r"\b(create|add|post|publish)\b.*\bannouncements?\b",
            "create_announcement",
        ),
        (
            r"\b(upload|add|create)\b.*\b(policies|policy|documents?)\b",
            "upload_policy",
        ),
    )
    for pattern, tool in patterns:
        if re.search(pattern, normalized):
            return tool
    return None


def _target_id(state: AgentState, key: str) -> uuid.UUID:
    payload = state.get("action_payload", {})
    raw_id = payload.get(key)
    if raw_id is None:
        match = UUID_PATTERN.search(state["message"])
        raw_id = match.group() if match else None
    if raw_id is None:
        raise WriteToolConflict(f"Missing required field: {key}.")
    try:
        return uuid.UUID(str(raw_id))
    except ValueError as exc:
        raise WriteToolConflict(f"Invalid {key}.") from exc


def _department_data(state: AgentState) -> DepartmentCreate:
    payload = dict(state.get("action_payload", {}))
    if not payload.get("name"):
        match = re.search(
            r"\bdepartment(?:\s+named)?\s+[\"']?([a-zA-Z][a-zA-Z &-]{1,99})[\"']?$",
            state["message"].strip(),
            flags=re.IGNORECASE,
        )
        if match:
            payload["name"] = match.group(1).strip()
    return DepartmentCreate.model_validate(payload)


def _extract_initial_payload(
    tool: ActionToolName, state: AgentState
) -> dict[str, object]:
    payload = dict(state.get("action_payload", {}))
    message = state["message"].strip()
    uuid_match = UUID_PATTERN.search(message)
    if uuid_match and tool in {"update_employee", "delete_employee"}:
        payload.setdefault("employee_id", uuid_match.group())
    if uuid_match and tool in {"approve_leave", "reject_leave", "cancel_leave"}:
        payload.setdefault("request_id", uuid_match.group())
    if uuid_match and tool == "delete_policy":
        payload.setdefault("document_id", uuid_match.group())

    if tool == "create_employee":
        name_match = re.search(
            r"\bemployee(?:\s+named)?\s+([A-Za-z][A-Za-z'-]+)"
            r"(?:\s+([A-Za-z][A-Za-z'-]+))?",
            message,
            flags=re.IGNORECASE,
        )
        if name_match:
            payload.setdefault("first_name", name_match.group(1).title())
            if name_match.group(2):
                payload.setdefault("last_name", name_match.group(2).title())
        email_match = EMAIL_PATTERN.search(message)
        date_match = DATE_PATTERN.search(message)
        if email_match:
            payload.setdefault("email", email_match.group())
        if date_match:
            payload.setdefault("date_of_joining", date_match.group())

    if tool == "create_department" and not payload.get("name"):
        match = re.search(
            r"\bdepartment(?:\s+named)?\s+(.+)$", message, flags=re.IGNORECASE
        )
        if match:
            payload["name"] = match.group(1).strip(" \"'")

    if tool in {"create_announcement", "upload_policy"} and not payload.get("title"):
        quoted_title = re.search(r"[\"']([^\"']+)[\"']", message)
        if quoted_title:
            payload["title"] = quoted_title.group(1).strip()

    normalized = message.lower()
    if tool == "delete_employee" and (
        "delete all" in normalized or "bulk" in normalized
    ):
        payload["bulk"] = True
        payload.pop("employee_id", None)
    return payload


def _missing_field(tool: ActionToolName, payload: dict[str, object]) -> str | None:
    if tool == "delete_employee" and payload.get("bulk"):
        return None
    for field in REQUIRED_FIELDS[tool]:
        value = payload.get(field)
        if value is None or value == "" or (field == "updates" and not value):
            return field
    return None


async def _validate_employee_email(payload: dict[str, object], db) -> str | None:
    """Validate and normalize agent-provided email before collecting more slots."""
    raw_email = payload.get("email")
    if raw_email in (None, ""):
        return None
    try:
        email = EMAIL_ADAPTER.validate_python(raw_email)
    except ValidationError:
        payload.pop("email", None)
        return (
            "That email address is invalid. Enter a valid email address, "
            "for example name@gmail.com."
        )

    payload["email"] = email
    existing = await db.scalar(
        select(User.id).where(func.lower(User.email) == email).limit(1)
    )
    if existing is not None:
        payload.pop("email", None)
        return "That email is already registered. Enter a different email address."
    return None


def _merge_slot_answer(
    field: str, message: str, supplied: dict[str, object], payload: dict[str, object]
) -> bool:
    payload.update(supplied)
    if field in supplied:
        return field == "password"
    normalized = message.strip()
    if field == "email":
        match = EMAIL_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field == "date_of_joining":
        match = DATE_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field in {"employee_id", "request_id"}:
        match = UUID_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field == "updates":
        if supplied:
            payload[field] = supplied.get("updates", supplied)
    else:
        payload[field] = normalized
    return field == "password"


def _pending_result(
    tool: ActionToolName,
    payload: dict[str, object],
    stage: str,
    message: str,
    missing_field: str | None = None,
) -> tuple[AgentToolResult, dict[str, object]]:
    pending: dict[str, object] = {
        "tool": tool,
        "stage": stage,
        "parameters": payload,
    }
    if missing_field:
        pending["missing_field"] = missing_field
    result_status = (
        "confirmation_required" if stage == "confirmation" else "needs_input"
    )
    interaction: dict[str, object] = {"stage": stage}
    if missing_field:
        interaction["missing_field"] = missing_field
    if tool == "upload_policy" and missing_field == "policy_file":
        interaction["parameters"] = {
            "title": payload.get("title", ""),
            "category": payload.get("category", ""),
        }
    elif tool == "update_employee" and missing_field == "updates":
        interaction["parameters"] = {
            "employee_id": payload.get("employee_id", ""),
        }
    return (
        {
            "agent": "action",
            "status": result_status,
            "tool": tool,
            "message": message,
            "data": interaction,
        },
        pending,
    )


def _confirmation_prompt(tool: ActionToolName, payload: dict[str, object]) -> str:
    if tool == "delete_employee" and payload.get("bulk"):
        return (
            "This is a bulk destructive request. No records have been changed. "
            "Reply 'confirm' to continue or 'cancel' to stop."
        )
    if tool == "apply_leave":
        return (
            f"Please confirm your leave request from {payload.get('start_date')} to "
            f"{payload.get('end_date')} for: {payload.get('reason')}. "
            "No request has been submitted yet. Reply 'confirm' or 'cancel'."
        )
    labels = {
        "delete_employee": "delete this employee",
        "approve_leave": "approve this leave request",
        "reject_leave": "reject this leave request",
        "create_announcement": "publish this announcement",
        "apply_leave": "submit this leave request",
        "cancel_leave": "cancel this leave request",
        "delete_policy": "permanently delete this policy document",
    }
    return (
        f"Please confirm that you want to {labels[tool]}. "
        "No changes have been made yet. Reply 'confirm' or 'cancel'."
    )


def _execution_state(
    state: AgentState, tool: ActionToolName, payload: dict[str, object]
) -> AgentState:
    messages = {
        "create_employee": "Create employee",
        "update_employee": "Update employee",
        "delete_employee": "Delete employee",
        "approve_leave": "Approve leave request",
        "reject_leave": "Reject leave request",
        "create_department": "Create department",
        "create_announcement": "Create announcement",
        "upload_policy": "Upload policy",
        "delete_policy": "Delete policy",
        "apply_leave": "Apply for leave",
        "cancel_leave": "Cancel leave request",
        "check_in": "Check in",
        "check_out": "Check out",
    }
    return {**state, "message": messages[tool], "action_payload": payload}


async def run_action(state: AgentState, db) -> AgentToolResult:
    """Execute a complete and already-confirmed action."""
    tool = select_action_tool(state["message"])
    if tool is None:
        return {
            "agent": "action",
            "status": "error",
            "tool": "unknown",
            "message": "I could not identify the requested HR action.",
        }

    payload = dict(state.get("action_payload", {}))
    if tool == "create_employee":
        data = await create_employee(state, db, EmployeeCreate.model_validate(payload))
        message = f"Created employee {data['full_name']}."
    elif tool == "update_employee":
        employee_id = _target_id(state, "employee_id")
        update_data = payload.get("updates", payload)
        if isinstance(update_data, dict):
            update_data = {k: v for k, v in update_data.items() if k != "employee_id"}
        data = await update_employee(
            state, db, employee_id, EmployeeUpdate.model_validate(update_data)
        )
        message = f"Updated employee {data['full_name']}."
    elif tool == "delete_employee":
        data = await delete_employee(state, db, _target_id(state, "employee_id"))
        message = "Employee deleted successfully."
    elif tool == "approve_leave":
        data = await approve_leave(state, db, _target_id(state, "request_id"))
        message = "Leave request approved."
    elif tool == "reject_leave":
        data = await reject_leave(state, db, _target_id(state, "request_id"))
        message = "Leave request rejected."
    elif tool == "create_announcement":
        data = await create_announcement(
            state, db, AnnouncementCreate.model_validate(payload)
        )
        message = f"Published announcement {data['title']}."
    elif tool == "upload_policy":
        data = await complete_policy_upload(
            state, db, _target_id(state, "document_id")
        )
        message = f"Uploaded and indexed policy {data['title']}."
    elif tool == "delete_policy":
        data = await delete_policy(state, db, _target_id(state, "document_id"))
        message = f"Deleted policy {data['title']} and its indexed content."
    elif tool == "apply_leave":
        data = await apply_leave(
            state, db, LeaveRequestCreate.model_validate(payload)
        )
        message = "Your leave request was submitted and is pending approval."
    elif tool == "cancel_leave":
        data = await cancel_leave(state, db, _target_id(state, "request_id"))
        message = "Your leave request was cancelled."
    elif tool in {"check_in", "check_out"}:
        data = await record_attendance_action(state, db, tool)
        message = (
            "Checked in successfully."
            if tool == "check_in"
            else "Checked out successfully."
        )
    else:
        data = await create_department(state, db, _department_data(state))
        message = f"Created department {data['name']}."
    return {
        "agent": "action",
        "status": "success",
        "tool": tool,
        "message": message,
        "data": data,
    }


async def handle_action(
    state: AgentState, db
) -> tuple[AgentToolResult, dict[str, object] | None, bool]:
    """Collect missing slots, gate sensitive actions, then execute."""
    pending = state.get("pending_action")
    if pending and select_action_tool(state["message"]) is not None:
        # A clear new action request replaces an abandoned pending action instead
        # of being interpreted as a slot value or confirm/cancel response.
        pending = None
    sanitized = False
    if pending:
        raw_tool = pending.get("tool")
        if raw_tool not in REQUIRED_FIELDS:
            raise WriteToolConflict(
                "The pending action is invalid. Please start again."
            )
        tool = cast(ActionToolName, raw_tool)
        payload = dict(cast(dict, pending.get("parameters", {})))
        await authorize_write_tool(state, db, tool)
        stage = pending.get("stage")
        answer = " ".join(state["message"].lower().split())
        if answer in CANCELLATION_WORDS:
            return (
                {
                    "agent": "action",
                    "status": "cancelled",
                    "tool": tool,
                    "message": "Action cancelled. No changes were made.",
                },
                None,
                False,
            )
        if stage == "confirmation":
            if answer not in CONFIRMATION_WORDS:
                result, unchanged = _pending_result(
                    tool,
                    payload,
                    "confirmation",
                    "Please reply 'confirm' to continue or 'cancel' to stop.",
                )
                return result, unchanged, False
            if payload.get("bulk"):
                return (
                    {
                        "agent": "action",
                        "status": "error",
                        "tool": tool,
                        "message": (
                            "Bulk employee deletion is not enabled. No records were changed."
                        ),
                    },
                    None,
                    False,
                )
            return (
                await run_action(_execution_state(state, tool, payload), db),
                None,
                False,
            )

        field = str(pending.get("missing_field", ""))
        sanitized = _merge_slot_answer(
            field, state["message"], state.get("action_payload", {}), payload
        )
    else:
        selected = select_action_tool(state["message"])
        if selected is None:
            return (
                {
                    "agent": "action",
                    "status": "error",
                    "tool": "unknown",
                    "message": "I could not identify the requested HR action.",
                },
                None,
                False,
            )
        tool = selected
        await authorize_write_tool(state, db, tool)
        payload = _extract_initial_payload(tool, state)

    if tool == "create_employee":
        email_error = await _validate_employee_email(payload, db)
        if email_error:
            payload.pop("password", None)
            result, next_pending = _pending_result(
                tool, payload, "slots", email_error, "email"
            )
            return result, next_pending, sanitized

    missing = _missing_field(tool, payload)
    if missing:
        if missing != "password":
            payload.pop("password", None)
        result, next_pending = _pending_result(
            tool, payload, "slots", FIELD_PROMPTS[missing], missing
        )
        return result, next_pending, sanitized

    if tool in SENSITIVE_ACTIONS:
        result, next_pending = _pending_result(
            tool, payload, "confirmation", _confirmation_prompt(tool, payload)
        )
        return result, next_pending, sanitized

    return await run_action(_execution_state(state, tool, payload), db), None, sanitized


async def action_agent_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    pending_action: dict[str, object] | None = state.get("pending_action")
    selected_tool = select_action_tool(state["message"])
    attempted_tool = selected_tool or (
        pending_action.get("tool") if pending_action else None
    )
    sanitized = False
    try:
        result, pending_action, sanitized = await handle_action(
            state, runtime.context["db"]
        )
    except WriteToolAccessDenied as exc:
        result = {
            "agent": "action",
            "status": "denied",
            "tool": str(attempted_tool or "unknown"),
            "message": str(exc),
        }
        pending_action = None
    except (WriteToolConflict, ValidationError, HTTPException) as exc:
        if pending_action and pending_action.get("stage") == "confirmation":
            # Execution was attempted and failed. Do not trap the next user
            # message inside a confirmation that can no longer succeed.
            pending_action = None
        if isinstance(exc, ValidationError):
            fields = sorted(
                {".".join(map(str, error["loc"])) for error in exc.errors()}
            )
            detail = "Missing or invalid fields: " + ", ".join(fields) + "."
        elif isinstance(exc, HTTPException):
            detail = str(exc.detail)
        else:
            detail = str(exc)
        result = {
            "agent": "action",
            "status": "error",
            "tool": str(attempted_tool or "unknown"),
            "message": detail,
        }
    output: dict[str, object] = {
        "tool_results": [result],
        "route_trace": ["action_agent"],
        "pending_action": pending_action,
    }
    if sanitized:
        output["memory_user_message"] = "[Sensitive value provided]"
    return output
