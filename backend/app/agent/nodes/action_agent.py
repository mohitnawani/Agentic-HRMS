"""Permission-controlled actions with slot filling and confirmation gates."""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from fastapi import HTTPException
from langgraph.runtime import Runtime
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.agent.audit import audit_tool_result
from app.agent.flows import TOOL_WORKFLOWS, missing_slots
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
    preview_leave_application,
    record_attendance_action,
    reject_leave,
    update_employee,
)
from app.models.department import Department
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.policy_document import PolicyDocument
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
CONFIRMATION_WORDS.update({"go ahead", "do it", "haan", "haan kar do", "ok proceed"})
CANCELLATION_WORDS = {
    "no",
    "n",
    "cancel",
    "stop",
    "abort",
    "never mind",
    "nevermind",
    "leave it",
    "forget it",
    "nahi",
    "rehne do",
}
PENDING_MAX_TURNS = 6
PENDING_MAX_AGE = timedelta(minutes=10)

FIELD_PROMPTS = {
    "first_name": "What is the employee's first name?",
    "last_name": "What is the employee's last name?",
    "email": "What is the employee's email address?",
    "date_of_joining": "What is the joining date? Please use YYYY-MM-DD.",
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
        (
            (
                r"^\s*(?:i\s+want\s+to\s+)?(?:delete|remove)\s+"
                r"(?:the\s+)?[A-Za-z][A-Za-z' -]{0,199}\s*$"
            ),
            "delete_employee",
        ),
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
    supplied_employee = payload.pop("employee", None)
    if supplied_employee and not payload.get("employee_id"):
        payload["employee_name"] = str(supplied_employee).strip()
    uuid_match = UUID_PATTERN.search(message)
    if uuid_match and tool in {"update_employee", "delete_employee"}:
        payload.setdefault("employee_id", uuid_match.group())
    if uuid_match and tool in {"approve_leave", "reject_leave", "cancel_leave"}:
        payload.setdefault("request_id", uuid_match.group())
    if uuid_match and tool == "delete_policy":
        payload.setdefault("document_id", uuid_match.group())

    if tool in {"update_employee", "delete_employee"} and not payload.get(
        "employee_id"
    ):
        name_match = re.search(
            r"\b(?:update|change|edit|delete|remove)\b\s+(?:the\s+)?"
            r"(?:employee|user)\s+([A-Za-z][A-Za-z' -]{0,199})$",
            message,
            flags=re.IGNORECASE,
        )
        if name_match:
            payload.setdefault("employee_name", name_match.group(1).strip())
        else:
            direct_name = re.search(
                r"^\s*(?:i\s+want\s+to\s+)?(?:delete|remove)\s+"
                r"(?:the\s+)?([A-Za-z][A-Za-z' -]{0,199})\s*$",
                message,
                flags=re.IGNORECASE,
            )
            if direct_name:
                payload.setdefault("employee_name", direct_name.group(1).strip())

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


async def _resolve_employee_name(
    payload: dict[str, object], db
) -> str | None:
    """Resolve a human name in code and refuse to guess when it is ambiguous."""
    if (
        payload.get("bulk")
        or payload.get("employee_id")
        or not payload.get("employee_name")
    ):
        return None
    candidate = " ".join(str(payload["employee_name"]).lower().split())
    rows = (
        await db.execute(
            select(Employee, Department.name)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(
                (func.lower(Employee.first_name) == candidate)
                | (func.lower(Employee.last_name) == candidate)
                | (
                    func.lower(func.concat(Employee.first_name, " ", Employee.last_name))
                    == candidate
                )
            )
            .order_by(Employee.first_name, Employee.last_name)
            .limit(10)
        )
    ).all()
    if len(rows) == 1:
        payload["employee_id"] = str(rows[0][0].id)
        return None
    if not rows:
        payload.pop("employee_name", None)
        return f"I could not find an employee named {candidate.title()}. Select an employee."
    options = "; ".join(
        f"{employee.first_name} {employee.last_name} "
        f"({department or 'No department'}, ID: {employee.id})"
        for employee, department in rows
    )
    return f"I found multiple matching employees: {options}. Select the correct employee."


def _missing_field(tool: ActionToolName, payload: dict[str, object]) -> str | None:
    missing = missing_slots(tool, payload)
    return missing[0] if missing else None


def _pending_expired(pending: dict[str, object]) -> bool:
    if int(pending.get("turns", 0)) >= PENDING_MAX_TURNS:
        return True
    raw_started = pending.get("started_at")
    if not isinstance(raw_started, str):
        return False
    try:
        started = datetime.fromisoformat(raw_started)
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return datetime.now(UTC) - started > PENDING_MAX_AGE


async def _confirmation_edits(
    tool: ActionToolName,
    message: str,
    supplied: dict[str, object],
    db,
) -> dict[str, object]:
    """Extract only explicit edits while a confirmation is pending."""
    edits = dict(supplied)
    normalized = " ".join(message.strip().split())
    lower = normalized.lower()
    dates = DATE_PATTERN.findall(normalized)
    if tool == "apply_leave":
        if "start" in lower and dates:
            edits.setdefault("start_date", dates[0])
        if "end" in lower and dates:
            edits.setdefault("end_date", dates[-1])
        reason_match = re.search(
            r"\breason\s+(?:to|is)\s+(.+)$", normalized, re.IGNORECASE
        )
        if reason_match:
            edits.setdefault("reason", reason_match.group(1).strip())
        leave_types = list((await db.scalars(select(LeaveType))).all())
        matched = [leave_type for leave_type in leave_types if leave_type.name.lower() in lower]
        if len(matched) == 1:
            edits.setdefault("leave_type_id", str(matched[0].id))
    return edits


async def _enrich_confirmation(
    tool: ActionToolName, payload: dict[str, object], db
) -> None:
    """Resolve affected records before confirmation; never ask users to sign blanks."""
    if tool in {"update_employee", "delete_employee"} and payload.get("employee_id"):
        employee_id = uuid.UUID(str(payload["employee_id"]))
        row = (
            await db.execute(
                select(Employee, Department.name)
                .outerjoin(Department, Department.id == Employee.department_id)
                .where(Employee.id == employee_id)
            )
        ).one_or_none()
        if row is None:
            raise WriteToolConflict("Employee not found.")
        employee, department = row
        payload["_target_summary"] = (
            f"{employee.first_name} {employee.last_name} "
            f"({department or 'No department'}, ID: {employee.id})"
        )
    elif tool in {"approve_leave", "reject_leave", "cancel_leave"} and payload.get(
        "request_id"
    ):
        request_id = uuid.UUID(str(payload["request_id"]))
        row = (
            await db.execute(
                select(LeaveRequest, Employee, LeaveType)
                .join(Employee, Employee.id == LeaveRequest.employee_id)
                .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
                .where(LeaveRequest.id == request_id)
            )
        ).one_or_none()
        if row is None:
            raise WriteToolConflict("Leave request not found.")
        request, employee, leave_type = row
        payload["_target_summary"] = (
            f"{employee.first_name} {employee.last_name}: {leave_type.name}, "
            f"{request.start_date} to {request.end_date}"
        )
    elif tool == "delete_policy" and payload.get("document_id"):
        document = await db.get(PolicyDocument, uuid.UUID(str(payload["document_id"])))
        if document is None:
            raise WriteToolConflict("Policy document not found.")
        payload["_target_summary"] = f"{document.title} ({document.category})"


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
    previous: dict[str, object] | None = None,
) -> tuple[AgentToolResult, dict[str, object]]:
    started_at = (
        previous.get("started_at")
        if previous and isinstance(previous.get("started_at"), str)
        else datetime.now(UTC).isoformat()
    )
    pending: dict[str, object] = {
        "tool": tool,
        "stage": stage,
        "parameters": payload,
        "started_at": started_at,
        "turns": int(previous.get("turns", 0)) + 1 if previous else 0,
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
            "Please confirm your leave request:\n"
            f"Type: {payload.get('_leave_type_name', payload.get('leave_type_id'))}\n"
            f"Dates: {payload.get('start_date')} to {payload.get('end_date')} "
            f"({payload.get('_days_requested')} day(s))\n"
            f"Reason: {payload.get('reason')}\n"
            f"Balance after: {payload.get('_remaining_after')} day(s)\nConfirm?"
        )
    if tool == "create_employee":
        return (
            "Please confirm creating this employee:\n"
            f"Name: {payload.get('first_name')} {payload.get('last_name')}\n"
            f"Email: {payload.get('email')}\n"
            f"Joining date: {payload.get('date_of_joining')}\n"
            "A temporary password will be generated securely. Confirm?"
        )
    if tool == "update_employee":
        fields = payload.get("updates", {})
        names = ", ".join(fields) if isinstance(fields, dict) else "selected fields"
        return (
            f"Update {payload.get('_target_summary', 'this employee')}: {names}. "
            "No changes have been made. Confirm?"
        )
    if tool == "create_department":
        return f"Create department: {payload.get('name')}. Confirm?"
    if tool == "create_announcement":
        return (
            f"Publish announcement: {payload.get('title')}\n"
            f"Message: {payload.get('body')}\nConfirm?"
        )
    if tool == "upload_policy":
        return (
            f"Finish policy upload: {payload.get('title')} "
            f"({payload.get('category')}). Confirm?"
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
    if tool == "delete_employee":
        return (
            "This will permanently delete 1 employee record and deactivate its "
            f"account: {payload.get('_target_summary', payload.get('employee_id'))}. "
            "Confirm?"
        )
    if tool in {"approve_leave", "reject_leave", "cancel_leave", "delete_policy"}:
        return (
            f"Please confirm: {labels[tool]} — "
            f"{payload.get('_target_summary', 'selected record')}. Confirm?"
        )
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
        temporary_password = secrets.token_urlsafe(12)
        payload["password"] = temporary_password
        data = await create_employee(state, db, EmployeeCreate.model_validate(payload))
        message = (
            f"Created employee {data['full_name']}. Temporary password: "
            f"{temporary_password}. Share it securely; it is shown only once."
        )
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
    requested_tool = select_action_tool(state["message"])
    if (
        pending
        and requested_tool is not None
        and requested_tool != pending.get("tool")
        and pending.get("stage") != "switch_confirmation"
    ):
        # A different write request never silently destroys the current flow.
        await authorize_write_tool(state, db, requested_tool)
        current_tool = str(pending.get("tool", "current action")).replace("_", " ")
        next_tool = requested_tool.replace("_", " ")
        replacement = {
            "tool": pending.get("tool"),
            "stage": "switch_confirmation",
            "original_stage": pending.get("stage", "slots"),
            "parameters": pending.get("parameters", {}),
            "missing_field": pending.get("missing_field"),
            "started_at": pending.get("started_at", datetime.now(UTC).isoformat()),
            "turns": int(pending.get("turns", 0)) + 1,
            "replacement_tool": requested_tool,
            "replacement_parameters": _extract_initial_payload(requested_tool, state),
        }
        return (
            {
                "agent": "action",
                "status": "confirmation_required",
                "tool": requested_tool,
                "message": (
                    f"You're partway through {current_tool}. Drop it and start "
                    f"{next_tool}? Reply 'confirm' or 'cancel'."
                ),
                "data": {"stage": "switch_confirmation"},
            },
            replacement,
            False,
        )
    if pending and requested_tool == pending.get("tool"):
        # Repeating the same action explicitly starts a clean copy of that flow.
        pending = None
    sanitized = False
    if pending:
        raw_tool = pending.get("tool")
        if raw_tool not in TOOL_WORKFLOWS:
            raise WriteToolConflict(
                "The pending action is invalid. Please start again."
            )
        tool = cast(ActionToolName, raw_tool)
        if _pending_expired(pending):
            return (
                {
                    "agent": "action",
                    "status": "cancelled",
                    "tool": tool,
                    "message": "That request expired. Start the action again when ready.",
                },
                None,
                False,
            )
        payload = dict(cast(dict, pending.get("parameters", {})))
        await authorize_write_tool(state, db, tool)
        stage = pending.get("stage")
        answer = " ".join(state["message"].lower().split())
        if stage == "switch_confirmation":
            if answer in CONFIRMATION_WORDS:
                replacement_tool = pending.get("replacement_tool")
                if replacement_tool not in TOOL_WORKFLOWS:
                    raise WriteToolConflict("The replacement action is invalid.")
                tool = cast(ActionToolName, replacement_tool)
                payload = dict(cast(dict, pending.get("replacement_parameters", {})))
                await authorize_write_tool(state, db, tool)
                pending = None
            elif answer in CANCELLATION_WORDS:
                original_stage = str(pending.get("original_stage", "slots"))
                original_field = pending.get("missing_field")
                original: dict[str, object] = {
                    "tool": tool,
                    "stage": original_stage,
                    "parameters": payload,
                    "started_at": pending.get("started_at"),
                    "turns": int(pending.get("turns", 0)) + 1,
                }
                if original_field:
                    original["missing_field"] = original_field
                return (
                    {
                        "agent": "action",
                        "status": (
                            "confirmation_required"
                            if original_stage == "confirmation"
                            else "needs_input"
                        ),
                        "tool": tool,
                        "message": "Kept the current action. Continue it or cancel it.",
                        "data": {
                            "stage": original_stage,
                            **(
                                {"missing_field": original_field}
                                if original_field
                                else {}
                            ),
                        },
                    },
                    original,
                    False,
                )
            else:
                return (
                    {
                        "agent": "action",
                        "status": "confirmation_required",
                        "tool": str(pending.get("replacement_tool", "unknown")),
                        "message": "Reply 'confirm' to switch actions or 'cancel' to keep the current one.",
                        "data": {"stage": "switch_confirmation"},
                    },
                    pending,
                    False,
                )
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
                edits = await _confirmation_edits(
                    tool, state["message"], state.get("action_payload", {}), db
                )
                if edits:
                    payload.update(edits)
                    if tool == "apply_leave":
                        preview = await preview_leave_application(
                            state, db, LeaveRequestCreate.model_validate(payload)
                        )
                        payload.update(
                            {f"_{key}": value for key, value in preview.items()}
                        )
                    result, changed = _pending_result(
                        tool,
                        payload,
                        "confirmation",
                        "Updated the requested details. "
                        + _confirmation_prompt(tool, payload),
                        previous=pending,
                    )
                    return result, changed, False
                result, unchanged = _pending_result(
                    tool,
                    payload,
                    "confirmation",
                    "Please reply 'confirm' to continue or 'cancel' to stop.",
                    previous=pending,
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

        if pending is not None:
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
            result, next_pending = _pending_result(
                tool, payload, "slots", email_error, "email", previous=pending
            )
            return result, next_pending, sanitized

    if tool in {"update_employee", "delete_employee"}:
        resolution_error = await _resolve_employee_name(payload, db)
        if resolution_error:
            result, next_pending = _pending_result(
                tool,
                payload,
                "slots",
                resolution_error,
                "employee_id",
                previous=pending,
            )
            return result, next_pending, sanitized

    missing = _missing_field(tool, payload)
    if missing:
        result, next_pending = _pending_result(
            tool,
            payload,
            "slots",
            FIELD_PROMPTS[missing],
            missing,
            previous=pending,
        )
        return result, next_pending, sanitized

    if tool == "apply_leave":
        preview = await preview_leave_application(
            state, db, LeaveRequestCreate.model_validate(payload)
        )
        payload.update({f"_{key}": value for key, value in preview.items()})

    if TOOL_WORKFLOWS[tool].confirmation != "none":
        await _enrich_confirmation(tool, payload, db)
        result, next_pending = _pending_result(
            tool,
            payload,
            "confirmation",
            _confirmation_prompt(tool, payload),
            previous=pending,
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
    if result.get("status") == "success" and result.get("tool") == "create_employee":
        output["memory_assistant_message"] = (
            "Employee created. The temporary password was shown once and is not stored "
            "in conversation history."
        )
    if result.get("status") in {"success", "denied", "error"}:
        await audit_tool_result(runtime.context["db"], state, result)
    return output
