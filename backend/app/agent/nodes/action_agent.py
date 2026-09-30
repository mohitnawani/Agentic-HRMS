"""Permission-controlled actions with slot filling and confirmation gates."""

import re
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

from fastapi import HTTPException
from langgraph.runtime import Runtime
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.agent.audit import audit_tool_result
from app.agent.flows import TOOL_WORKFLOWS, missing_slots
from app.agent.state import AgentRuntimeContext, AgentState, AgentToolResult
from app.agent.tools.read_tools import get_leave_history, list_pending_leave_requests
from app.agent.tools.write_tools import (
    WriteToolAccessDenied,
    WriteToolConflict,
    apply_leave,
    approve_leave,
    authorize_write_tool,
    cancel_leave,
    complete_policy_upload,
    correct_employee_attendance,
    create_announcement,
    create_department,
    create_designation,
    create_employee,
    create_holiday,
    create_leave_type,
    delete_announcement,
    delete_department,
    delete_designation,
    delete_employee,
    delete_holiday,
    delete_policy,
    preview_leave_application,
    record_attendance_action,
    reject_leave,
    update_announcement,
    update_employee,
    update_policy,
)
from app.models.announcement import Announcement
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.designation import Designation
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.models.leave import LeaveRequest, LeaveType
from app.models.policy_document import PolicyDocument
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.schemas.attendance import AttendanceDateCorrection
from app.schemas.common import EmailT
from app.schemas.department import DepartmentCreate
from app.schemas.designation import DesignationCreate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.schemas.holiday import HolidayCreate
from app.schemas.leave import LeaveRequestCreate, LeaveTypeCreate

ActionToolName = Literal[
    "create_employee",
    "update_employee",
    "upload_employee_photo",
    "delete_employee",
    "approve_leave",
    "reject_leave",
    "create_leave_type",
    "create_department",
    "delete_department",
    "create_designation",
    "delete_designation",
      "create_announcement",
      "update_announcement",
      "delete_announcement",
    "create_holiday",
    "delete_holiday",
    "upload_policy",
    "update_policy",
    "delete_policy",
    "apply_leave",
    "cancel_leave",
    "check_in",
    "check_out",
    "correct_attendance",
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
    "exit",
    "exit flow",
    "quit",
    "never mind",
    "nevermind",
    "leave it",
    "forget it",
    "nahi",
    "rehne do",
}
PENDING_MAX_TURNS = 6
PENDING_MAX_AGE = timedelta(minutes=10)


def _assistant_role_name(state: AgentState) -> str:
    role = RoleEnum(state["role"])
    return {
        RoleEnum.ADMIN: "Admin",
        RoleEnum.HR: "HR",
        RoleEnum.EMPLOYEE: "Employee",
    }[role]

FIELD_PROMPTS = {
    "first_name": "What is the employee's first name?",
    "last_name": "What is the employee's last name?",
    "email": "What is the employee's email address?",
    "date_of_joining": "What is the joining date? Please use YYYY-MM-DD.",
    "role": "Which account role should this employee have?",
    "employee_id": "What is the employee ID?",
    "request_id": "What is the leave request ID?",
    "update_field": "Which employee field would you like to change?",
    "update_value": "What should the new value be?",
    "photo_file": "Choose the employee photo to upload.",
    "name": "What name should be used?",
    "department_id": "Which department should be used?",
    "designation_id": "Which designation should be deleted?",
    "announcement_id": "Which announcement should be deleted?",
    "announcement_title": "What should the announcement title be?",
    "announcement_body": "What should the announcement message say?",
    "announcement_is_active": "Should this announcement be visible to users?",
    "holiday_id": "Which holiday should be deleted?",
    "title": "What title should be used?",
    "body": "What should the announcement say?",
    "category": "What category should this policy use?",
    "policy_title": "What should the policy title be?",
    "policy_category": "What should the policy category be?",
    "policy_file": "Choose the PDF policy file to upload.",
    "document_id": "Which policy document should be deleted?",
    "leave_type_id": "Which leave type would you like to use?",
    "start_date": "What is the leave start date? Please use YYYY-MM-DD.",
    "end_date": "What is the leave end date? Please use YYYY-MM-DD.",
    "reason": "What is the reason for your leave?",
    "date": "Which attendance date should be corrected?",
    "status": "What should the attendance status be?",
    "correction_reason": "Why is this attendance being corrected?",
    "leave_type_name": "What is the leave type name?",
    "annual_days": "How many days should employees receive each year?",
}


LEAVE_TYPE_PRESENTATION = {
    "Casual Leave": ("Casual Leave (CL)", "Short personal work or urgent needs"),
    "Sick Leave": ("Sick Leave (SL)", "Illness or medical reasons"),
    "Earned Leave / Privilege Leave": (
        "Earned Leave / Privilege Leave (EL/PL)",
        "Accumulated paid leave for planned time off",
    ),
    "Maternity Leave": ("Maternity Leave", "Childbirth and recovery"),
    "Paternity Leave": ("Paternity Leave", "Leave for new fathers"),
    "Bereavement Leave": ("Bereavement Leave", "Death of a close family member"),
    "Marriage Leave": ("Marriage Leave", "The employee's wedding"),
    "Compensatory Off": (
        "Compensatory Off (Comp Off)",
        "Earned by working on holidays or weekends",
    ),
    "Unpaid Leave / Loss of Pay": (
        "Unpaid Leave / Loss of Pay (LOP)",
        "Used when paid leave is unavailable",
    ),
}

EMPLOYEE_UPDATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("role", "Account role"),
    ("first_name", "First name"),
    ("last_name", "Last name"),
    ("phone", "Phone"),
    ("employee_code", "Employee code"),
    ("date_of_joining", "Joining date"),
    ("date_of_birth", "Date of birth"),
    ("gender", "Gender"),
    ("department_id", "Department"),
    ("designation_id", "Designation"),
    ("city", "City"),
    ("address", "Address"),
    ("emergency_contact", "Emergency contact"),
    ("bank_name", "Bank name"),
    ("account_number", "Account number"),
    ("ifsc_code", "IFSC code"),
    ("id_proof_type", "ID proof type"),
    ("id_proof_number", "ID proof number"),
)
EMPLOYEE_UPDATE_FIELD_NAMES = {name for name, _ in EMPLOYEE_UPDATE_FIELDS}
EMPLOYEE_UPDATE_FIELD_LABELS = dict(EMPLOYEE_UPDATE_FIELDS)


async def _slot_suggestions(
    tool: str,
    missing: str,
    state: AgentState,
    db,
    payload: dict[str, object] | None = None,
) -> tuple[list[dict[str, str]], str | None]:
    """Clickable options for the field being collected.

    Returns (suggestions, prompt_override). Only called after the tool's own
    authorization, so listing rows here never leaks beyond what the caller
    may already act on.
    """
    if missing == "employee_id":
        rows = list((await db.scalars(select(Employee).order_by(Employee.first_name, Employee.last_name).limit(30))).all())
        return [{"label": f"{row.first_name} {row.last_name}", "value": str(row.id)} for row in rows], None
    payload = payload or {}
    if missing == "update_field" and tool == "update_employee":
        return [
            {"label": label, "value": name}
            for name, label in EMPLOYEE_UPDATE_FIELDS
        ], "Which single employee field would you like to change?"
    if missing == "update_value" and tool == "update_employee":
        field = str(payload.get("update_field", ""))
        if field == "role":
            return [
                {"label": "Employee", "value": "employee"},
                {"label": "HR", "value": "hr"},
            ], None
        if field == "department_id":
            rows = list(
                (await db.scalars(select(Department).order_by(Department.name))).all()
            )
            return [{"label": row.name, "value": str(row.id)} for row in rows], None
        if field == "designation_id":
            rows = list(
                (await db.scalars(select(Designation).order_by(Designation.title))).all()
            )
            return [{"label": row.title, "value": str(row.id)} for row in rows], None
        if field == "gender":
            return [
                {"label": value, "value": value}
                for value in ("Female", "Male", "Non-binary", "Prefer not to say")
            ], None
    if missing == "department_id":
        rows = list((await db.scalars(select(Department).order_by(Department.name))).all())
        return [{"label": row.name, "value": str(row.id)} for row in rows], None
    if missing == "designation_id":
        rows = list((await db.scalars(select(Designation).order_by(Designation.title))).all())
        return [{"label": row.title, "value": str(row.id)} for row in rows], None
    if missing == "holiday_id":
        rows = list((await db.scalars(select(Holiday).order_by(Holiday.date))).all())
        return [{"label": f"{row.name} · {row.date}", "value": str(row.id)} for row in rows], None
    if missing == "announcement_id":
        rows = list((await db.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(30))).all())
        prompt = (
            "Which announcement would you like to edit?"
            if tool == "update_announcement"
            else "Which announcement should be deleted?"
        )
        return [{"label": row.title, "value": str(row.id)} for row in rows], prompt
    if missing == "user_id":
        rows = list((await db.scalars(select(User).order_by(User.email).limit(40))).all())
        return [{"label": f"{row.email} · {row.role.value}", "value": str(row.id)} for row in rows if row.id != state["user_id"]], None
    if missing == "attendance_id":
        rows = (await db.execute(select(Attendance, Employee).join(Employee, Employee.id == Attendance.employee_id).order_by(Attendance.date.desc()).limit(30))).all()
        return [{"label": f"{employee.first_name} {employee.last_name} · {record.date} · {record.status.value}", "value": str(record.id)} for record, employee in rows], None
    if missing == "document_id":
        rows = list((await db.scalars(select(PolicyDocument).order_by(PolicyDocument.title).limit(30))).all())
        prompt = (
            "Which policy would you like to edit?"
            if tool == "update_policy"
            else "Which policy document should be deleted?"
        )
        return [{"label": f"{row.title} · {row.category}", "value": str(row.id)} for row in rows], prompt
    if missing == "role":
        return [
            {"label": "Employee", "value": "employee"},
            {"label": "HR", "value": "hr"},
        ], "Should this account be an Employee or HR?"
    if missing == "active":
        return [{"label": "Activate", "value": "true"}, {"label": "Deactivate", "value": "false"}], None
    if missing == "announcement_is_active":
        options = [
            {"label": "Visible", "value": "true"},
            {"label": "Hidden", "value": "false"},
        ]
        if tool == "update_announcement":
            options.insert(0, {"label": "Keep current visibility", "value": "keep"})
        return options, None
    if missing == "status":
        return [{"label": value.replace("_", " ").title(), "value": value} for value in ("present", "absent", "late", "half_day")], None
    if tool == "apply_leave" and missing == "leave_type_id":
        leave_types = list((await db.scalars(select(LeaveType).order_by(LeaveType.name))).all())
        options = ", ".join(item.name for item in leave_types)
        prompt = f"Which leave type would you like to use? Available types: {options}." if options else None
        return [
            {
                "label": LEAVE_TYPE_PRESENTATION.get(item.name, (item.name, ""))[0],
                "value": str(item.id),
                "description": LEAVE_TYPE_PRESENTATION.get(item.name, (item.name, ""))[1],
            }
            for item in leave_types
        ], prompt
    if missing == "request_id" and tool in {"approve_leave", "reject_leave"}:
        requests = await list_pending_leave_requests(state, db)
        return [
            {
                "label": f"{item['employee']} · {item['leave_type']} · {item['start_date']} to {item['end_date']}",
                "value": str(item["request_id"]),
            }
            for item in requests[:12]
        ], None
    if missing == "request_id" and tool == "cancel_leave":
        requests = await get_leave_history(state, db)
        return [
            {
                "label": f"{item['leave_type']} · {item['start_date']} to {item['end_date']}",
                "value": str(item["request_id"]),
            }
            for item in requests
            if item["status"] == "pending"
        ][:12], None
    return [], None


def select_action_tool(message: str) -> ActionToolName | None:
    normalized = " ".join(message.lower().split())
    patterns: tuple[tuple[str, ActionToolName], ...] = (
        (
            r"\b(upload|change|update|replace)\b.*\b(employees?|users?)?\s*photo\b",
            "upload_employee_photo",
        ),
        (r"\b(create|add)\b.*\b(employees?|users?)\b", "create_employee"),
        (r"\b(update|change|edit)\b.*\b(employees?|users?)\b", "update_employee"),
        (r"\b(delete|remove)\b.*\b(employees?|users?)\b", "delete_employee"),
        (r"\b(delete|remove)\b.*\b(policies|policy|documents?)\b", "delete_policy"),
        (r"\b(update|change|edit|rename)\b.*\b(policies|policy|documents?)\b", "update_policy"),
        (r"\b(delete|remove)\b.*\bdepartments?\b", "delete_department"),
        (r"\b(delete|remove)\b.*\bdesignations?\b", "delete_designation"),
        (r"\b(delete|remove)\b.*\bannouncements?\b", "delete_announcement"),
        (r"\b(delete|remove)\b.*\bholidays?\b", "delete_holiday"),
        (
            (
                r"^\s*(?:i\s+want\s+to\s+)?(?:delete|remove)\s+"
                r"(?:the\s+)?[A-Za-z][A-Za-z' -]{0,199}\s*$"
            ),
            "delete_employee",
        ),
        (
            r"\b(approve|accept|grant)\b(?:.*\b(leaves?|requests?|approvals?|tasks?)\b)?",
            "approve_leave",
        ),
        (
            r"\b(reject|decline|deny)\b(?:.*\b(leaves?|requests?|approvals?|tasks?)\b)?",
            "reject_leave",
        ),
        (r"\b(create|add)\b.*\bleave\s+types?\b", "create_leave_type"),
        (r"\bapply\b.*\bleave\b", "apply_leave"),
        (r"\bcancel\b.*\bleave\b", "cancel_leave"),
        (r"\bcheck[ -]?in\b", "check_in"),
        (r"\bcheck[ -]?out\b", "check_out"),
        (
            r"\b(correct|fix|change|update)\b.*\battendance\b",
            "correct_attendance",
        ),
        (r"\b(create|add)\b.*\bdepartments?\b", "create_department"),
        (r"\b(create|add)\b.*\bdesignations?\b", "create_designation"),
        (r"\b(create|add)\b.*\bholidays?\b", "create_holiday"),
        (
            r"\b(create|add|post|publish)\b.*\bannouncements?\b",
            "create_announcement",
        ),
        (
            r"\b(update|change|edit)\b.*\bannouncements?\b",
            "update_announcement",
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
    if uuid_match and tool in {
        "update_employee",
        "upload_employee_photo",
        "delete_employee",
        "correct_attendance",
    }:
        payload.setdefault("employee_id", uuid_match.group())
    if uuid_match and tool in {"approve_leave", "reject_leave", "cancel_leave"}:
        payload.setdefault("request_id", uuid_match.group())
    if uuid_match and tool in {"delete_policy", "update_policy"}:
        payload.setdefault("document_id", uuid_match.group())
    id_fields = {
        "delete_department": "department_id",
        "delete_designation": "designation_id",
        "delete_announcement": "announcement_id",
        "delete_holiday": "holiday_id",
    }
    if uuid_match and tool == "update_announcement":
        payload.setdefault("announcement_id", uuid_match.group())
    if uuid_match and tool in id_fields:
        payload.setdefault(id_fields[tool], uuid_match.group())

    if tool in {
        "update_employee",
        "upload_employee_photo",
        "delete_employee",
        "correct_attendance",
    } and not payload.get(
        "employee_id"
    ):
        if tool == "upload_employee_photo":
            name_match = re.search(
                r"\b(?:upload|change|update|replace)\b\s+(?:the\s+)?"
                r"(?:employee|user)\s+([A-Za-z][A-Za-z' -]{0,199}?)\s+photo$",
                message,
                flags=re.IGNORECASE,
            )
        else:
            name_match = re.search(
                r"\b(?:update|change|edit|delete|remove|correct|fix)\b\s+(?:the\s+)?"
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

    if tool == "create_designation" and not payload.get("title"):
        match = re.search(
            r"\bdesignation(?:\s+(?:named|called))?\s+(.+?)(?:\s+in\s+department\b|$)",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            payload["title"] = match.group(1).strip(" \"'")

    if tool == "create_holiday":
        date_match = DATE_PATTERN.search(message)
        if date_match:
            payload.setdefault("date", date_match.group())
        if not payload.get("name"):
            match = re.search(
                r"\bholiday(?:\s+(?:named|called))?\s+(.+?)(?:\s+on\s+\d{4}-\d{2}-\d{2}|$)",
                message,
                flags=re.IGNORECASE,
            )
            if match:
                payload["name"] = match.group(1).strip(" \"'")

    if tool == "create_leave_type" and not payload.get("leave_type_name"):
        match = re.search(
            r"\bleave\s+type(?:\s+(?:named|called))?\s+(.+)$",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            payload["leave_type_name"] = match.group(1).strip(" \"'")

    if tool in {"create_announcement", "upload_policy"} and not payload.get("title"):
        quoted_title = re.search(r"[\"']([^\"']+)[\"']", message)
        if quoted_title:
            payload["title"] = quoted_title.group(1).strip()

    normalized = message.lower()
    if tool == "correct_attendance":
        date_match = DATE_PATTERN.search(message)
        if date_match:
            payload.setdefault("date", date_match.group())
        for attendance_status in ("present", "absent", "late", "half_day"):
            readable = attendance_status.replace("_", " ")
            if re.search(rf"\b{re.escape(readable)}\b", normalized):
                payload.setdefault("status", attendance_status)
                break
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
    return "I found multiple employees with that name. Select the correct employee."


async def _resolve_pending_leave_reference(
    tool: ActionToolName,
    payload: dict[str, object],
    message: str,
    state: AgentState,
    db,
) -> str | None:
    """Resolve a spoken employee name to one eligible pending leave request."""
    if tool not in {"approve_leave", "reject_leave"} or payload.get("request_id"):
        return None
    normalized = " ".join(message.lower().split())
    ignored = {
        "a",
        "accept",
        "approval",
        "approvals",
        "approve",
        "decline",
        "deny",
        "for",
        "grant",
        "leave",
        "leaves",
        "of",
        "reject",
        "request",
        "requests",
        "s",
        "task",
        "tasks",
        "the",
    }
    target_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if token not in ignored
    }
    if not target_terms:
        return None

    requests = await list_pending_leave_requests(state, db)
    matches = []
    for request in requests:
        employee_terms = set(
            re.findall(r"[a-z0-9]+", str(request.get("employee", "")).lower())
        )
        if target_terms <= employee_terms:
            matches.append(request)
    if len(matches) == 1:
        payload["request_id"] = str(matches[0]["request_id"])
        return None
    if len(matches) > 1:
        return (
            "I found multiple pending leave requests for that employee. "
            "Select the correct request by leave type and dates."
        )
    return (
        "I could not find an eligible pending leave request for that employee. "
        "Select one of the pending requests below."
    )


async def _prepare_employee_edit(
    payload: dict[str, object], db
) -> str | None:
    """Load the selected field's trusted current value and build one update.

    Chat edits deliberately collect one field per confirmed action. This keeps
    the interaction conversational and prevents a large manual edit form from
    bypassing the pending-action workflow.
    """
    raw_employee_id = payload.get("employee_id")
    if not raw_employee_id:
        return None
    try:
        employee_id = uuid.UUID(str(raw_employee_id))
    except ValueError:
        payload.pop("employee_id", None)
        return "Select a valid employee."

    row = (
        await db.execute(
            select(Employee, User)
            .join(User, User.id == Employee.user_id)
            .where(Employee.id == employee_id)
        )
    ).one_or_none()
    if row is None:
        payload.pop("employee_id", None)
        return "Employee not found. Select an employee."
    employee, user = row
    payload["_target_summary"] = f"{employee.first_name} {employee.last_name}"

    field = payload.get("update_field")
    if not field:
        return None
    field = str(field)
    if field not in EMPLOYEE_UPDATE_FIELD_NAMES:
        payload.pop("update_field", None)
        return "Choose one of the available employee fields."

    current_value = user.role.value if field == "role" else getattr(employee, field)
    current_display: object = current_value
    if field == "department_id" and current_value:
        record = await db.get(Department, current_value)
        current_display = record.name if record else current_value
    elif field == "designation_id" and current_value:
        record = await db.get(Designation, current_value)
        current_display = record.title if record else current_value
    payload["_current_update_value"] = (
        current_value.value if hasattr(current_value, "value") else current_value
    )
    payload["_current_update_display"] = current_display or "Not set"

    if "update_value" not in payload:
        return None
    value: object = payload["update_value"]
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in {"clear", "remove", "none", "not set"}:
            value = None
        elif field == "role":
            value = value.lower()
    try:
        validated = EmployeeUpdate.model_validate({field: value})
    except ValidationError as exc:
        payload.pop("update_value", None)
        payload.pop("updates", None)
        message = exc.errors()[0].get("msg", "Enter a valid value.")
        return f"That value is invalid for {EMPLOYEE_UPDATE_FIELD_LABELS[field].lower()}: {message}"
    payload["updates"] = validated.model_dump(exclude_unset=True, mode="json")
    return None


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
    if tool in {
        "update_employee",
        "upload_employee_photo",
        "delete_employee",
        "correct_attendance",
    } and payload.get("employee_id"):
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
    elif tool in {"delete_policy", "update_policy"} and payload.get("document_id"):
        document = await db.get(PolicyDocument, uuid.UUID(str(payload["document_id"])))
        if document is None:
            raise WriteToolConflict("Policy document not found.")
        payload["_target_summary"] = f"{document.title} ({document.category})"
    elif tool == "delete_department" and payload.get("department_id"):
        record = await db.get(Department, uuid.UUID(str(payload["department_id"])))
        if record is None:
            raise WriteToolConflict("Department not found.")
        payload["_target_summary"] = record.name
    elif tool == "delete_designation" and payload.get("designation_id"):
        record = await db.get(Designation, uuid.UUID(str(payload["designation_id"])))
        if record is None:
            raise WriteToolConflict("Designation not found.")
        payload["_target_summary"] = record.title
    elif tool in {"delete_announcement", "update_announcement"} and payload.get(
        "announcement_id"
    ):
        record = await db.get(Announcement, uuid.UUID(str(payload["announcement_id"])))
        if record is None:
            raise WriteToolConflict("Announcement not found.")
        payload["_target_summary"] = record.title
    elif tool == "delete_holiday" and payload.get("holiday_id"):
        record = await db.get(Holiday, uuid.UUID(str(payload["holiday_id"])))
        if record is None:
            raise WriteToolConflict("Holiday not found.")
        payload["_target_summary"] = f"{record.name} on {record.date}"
    elif tool == "create_designation" and payload.get("department_id"):
        department = await db.get(
            Department, uuid.UUID(str(payload["department_id"]))
        )
        if department is None:
            raise WriteToolConflict("Department not found.")
        payload["_department_name"] = department.name


async def _prepare_announcement_edit(payload: dict[str, object], db) -> None:
    """Load trusted current values for the guided announcement edit flow."""
    if not payload.get("announcement_id") or "_original_title" in payload:
        return
    try:
        announcement_id = uuid.UUID(str(payload["announcement_id"]))
    except ValueError as exc:
        raise WriteToolConflict("Select a valid announcement.") from exc
    record = await db.get(Announcement, announcement_id)
    if record is None:
        raise WriteToolConflict("Announcement not found.")
    payload.update(
        {
            "_original_title": record.title,
            "_original_body": record.body,
            "_original_is_active": record.is_active,
            "_target_summary": record.title,
        }
    )


def _announcement_updates(payload: dict[str, object]) -> dict[str, object]:
    """Return only changed fields after every edit step has been reviewed."""
    proposed = {
        "title": payload.get("announcement_title"),
        "body": payload.get("announcement_body"),
        "is_active": payload.get("announcement_is_active"),
    }
    return {
        field: value
        for field, value in proposed.items()
        if value != payload.get(f"_original_{field}")
    }


async def _prepare_policy_edit(payload: dict[str, object], db) -> None:
    if not payload.get("document_id") or "_original_title" in payload:
        return
    try:
        document_id = uuid.UUID(str(payload["document_id"]))
    except ValueError as exc:
        raise WriteToolConflict("Select a valid policy document.") from exc
    document = await db.get(PolicyDocument, document_id)
    if document is None:
        raise WriteToolConflict("Policy document not found.")
    payload.update(
        {
            "_original_title": document.title,
            "_original_category": document.category,
            "_target_summary": f"{document.title} ({document.category})",
        }
    )


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
    supplied_value = supplied.get(field)
    normalized = str(supplied_value if field in supplied else message).strip()
    if field in {"announcement_title", "announcement_body", "policy_title", "policy_category"}:
        field_name = field.removeprefix("announcement_").removeprefix("policy_")
        original_key = f"_original_{field_name}"
        payload[field] = (
            payload.get(original_key)
            if normalized.lower() in {"keep", "keep current", "same", "no change"}
            else normalized
        )
    elif field == "announcement_is_active":
        if normalized.lower() in {"keep", "keep current", "same", "no change"}:
            payload[field] = payload.get("_original_is_active")
        else:
            payload[field] = normalized.lower() in {"true", "yes", "visible", "active"}
    elif field in supplied:
        return field == "password"
    elif field == "email":
        match = EMAIL_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field in {"date_of_joining", "date"}:
        match = DATE_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field.endswith("_id"):
        match = UUID_PATTERN.search(normalized)
        payload[field] = match.group() if match else normalized
    elif field == "updates":
        if supplied:
            payload[field] = supplied.get("updates", supplied)
    elif field == "status":
        payload[field] = normalized.lower().replace("-", "_").replace(" ", "_")
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
    if tool in {"update_announcement", "update_policy"} and missing_field in {
        "announcement_title",
        "announcement_body",
        "announcement_is_active",
        "policy_title",
        "policy_category",
    }:
        field_name = missing_field.removeprefix("announcement_").removeprefix("policy_")
        original_key = f"_original_{field_name}"
        interaction["current_value"] = payload.get(original_key)
        interaction["allow_keep"] = True
    if tool == "update_employee" and missing_field == "update_value":
        interaction["current_value"] = payload.get("_current_update_display")
        selected_field = str(payload.get("update_field", ""))
        interaction["field_label"] = EMPLOYEE_UPDATE_FIELD_LABELS.get(
            selected_field, selected_field.replace("_", " ").title()
        )
        if selected_field in {"date_of_joining", "date_of_birth"}:
            interaction["input_type"] = "date"
    if missing_field == "end_date" and payload.get("start_date"):
        interaction["min_date"] = payload["start_date"]
    if tool == "upload_policy" and missing_field == "policy_file":
        interaction["parameters"] = {
            "title": payload.get("title", ""),
            "category": payload.get("category", ""),
        }
    elif tool == "upload_employee_photo" and missing_field == "photo_file":
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
            f"Role: {str(payload.get('role')).upper()}\n"
            "A temporary password will be generated securely. Confirm?"
        )
    if tool == "update_employee":
        fields = payload.get("updates", {})
        if isinstance(fields, dict):
            field, value = next(iter(fields.items()))
            label = EMPLOYEE_UPDATE_FIELD_LABELS.get(
                field, field.replace("_", " ").title()
            )
            current = payload.get("_current_update_display", "Not set")
            change = f"{label}: {current} -> {value if value is not None else 'Not set'}"
        else:
            change = "selected employee field"
        return (
            f"Update {payload.get('_target_summary', 'this employee')}\n{change}\n"
            "No changes have been made. Confirm?"
        )
    if tool == "update_announcement":
        fields = payload.get("updates", {})
        if isinstance(fields, dict):
            lines = "\n".join(
                f"- {field.replace('_', ' ').title()}: {value}"
                for field, value in fields.items()
            )
        else:
            lines = "Selected announcement fields"
        return (
            f"Update {payload.get('_target_summary', 'this announcement')} with:\n"
            f"{lines}\nNo changes have been made. Confirm?"
        )
    if tool == "create_department":
        return f"Create department: {payload.get('name')}. Confirm?"
    if tool == "create_designation":
        return (
            f"Create designation {payload.get('title')} in "
            f"{payload.get('_department_name', payload.get('department_id'))}. Confirm?"
        )
    if tool == "create_holiday":
        return f"Create holiday {payload.get('name')} on {payload.get('date')}. Confirm?"
    if tool == "create_leave_type":
        return (
            f"Create leave type {payload.get('leave_type_name')} with "
            f"{payload.get('annual_days')} days per year. Confirm?"
        )
    if tool == "create_announcement":
        return (
            f"Publish announcement: {payload.get('title')}\n"
            f"Message: {payload.get('body')}\n"
            f"Visibility: {'Visible' if payload.get('announcement_is_active') else 'Hidden'}\n"
            "Confirm?"
        )
    if tool == "correct_attendance":
        return (
            "Please confirm this attendance correction:\n"
            f"Employee: {payload.get('_target_summary', payload.get('employee_id'))}\n"
            f"Date: {payload.get('date')}\n"
            f"Status: {str(payload.get('status')).replace('_', ' ').title()}\n"
            f"Reason: {payload.get('correction_reason')}\nConfirm?"
        )
    if tool == "upload_policy":
        return (
            f"Finish policy upload: {payload.get('title')} "
            f"({payload.get('category')}). Confirm?"
        )
    if tool == "update_policy":
        changed: list[tuple[str, object]] = []
        if payload.get("policy_title") != payload.get("_original_title"):
            changed.append(("Title", payload.get("policy_title")))
        if payload.get("policy_category") != payload.get("_original_category"):
            changed.append(("Category", payload.get("policy_category")))
        change_lines = "\n".join(f"- {label}: {value}" for label, value in changed)
        return (
            f"Update policy {payload.get('_target_summary', '')}:\n"
            f"{change_lines}\n"
            "No changes have been made. Confirm?"
        )
    labels = {
        "delete_employee": "delete this employee",
        "approve_leave": "approve this leave request",
        "reject_leave": "reject this leave request",
        "create_announcement": "publish this announcement",
        "update_announcement": "update this announcement",
        "apply_leave": "submit this leave request",
        "cancel_leave": "cancel this leave request",
        "delete_policy": "permanently delete this policy document",
        "delete_department": "delete this department",
        "delete_designation": "delete this designation",
        "delete_announcement": "delete this announcement",
        "delete_holiday": "delete this holiday",
    }
    if tool == "delete_employee":
        return (
            "This will permanently delete 1 employee record and deactivate its "
            f"account: {payload.get('_target_summary', payload.get('employee_id'))}. "
            "Confirm?"
        )
    if tool in {
        "approve_leave", "reject_leave", "cancel_leave", "delete_policy",
        "delete_department", "delete_designation", "delete_announcement", "delete_holiday",
    }:
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
        "upload_employee_photo": "Upload employee photo",
        "delete_employee": "Delete employee",
        "approve_leave": "Approve leave request",
        "reject_leave": "Reject leave request",
        "create_leave_type": "Create leave type",
        "create_department": "Create department",
        "delete_department": "Delete department",
        "create_designation": "Create designation",
        "delete_designation": "Delete designation",
        "create_announcement": "Create announcement",
        "update_announcement": "Update announcement",
        "delete_announcement": "Delete announcement",
        "create_holiday": "Create holiday",
        "delete_holiday": "Delete holiday",
        "upload_policy": "Upload policy",
        "update_policy": "Update policy",
        "delete_policy": "Delete policy",
        "apply_leave": "Apply for leave",
        "cancel_leave": "Cancel leave request",
        "check_in": "Check in",
        "check_out": "Check out",
        "correct_attendance": "Correct attendance",
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
            "message": (
                f"I could not identify the requested {_assistant_role_name(state)} "
                "Assistant action."
            ),
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
    elif tool == "upload_employee_photo":
        employee_id = _target_id(state, "employee_id")
        employee = await db.get(Employee, employee_id)
        if employee is None:
            raise WriteToolConflict("Employee not found.")
        if not payload.get("photo_file") or not employee.photo_url:
            raise WriteToolConflict("The employee photo upload was not completed.")
        data = {
            "employee_id": str(employee.id),
            "photo_url": employee.photo_url,
        }
        message = f"Updated the photo for {employee.first_name} {employee.last_name}."
    elif tool == "delete_employee":
        data = await delete_employee(state, db, _target_id(state, "employee_id"))
        message = "Employee deleted successfully."
    elif tool == "approve_leave":
        data = await approve_leave(state, db, _target_id(state, "request_id"))
        message = "Leave request approved."
    elif tool == "reject_leave":
        data = await reject_leave(state, db, _target_id(state, "request_id"))
        message = "Leave request rejected."
    elif tool == "create_leave_type":
        data = await create_leave_type(
            state,
            db,
            LeaveTypeCreate.model_validate(
                {
                    "name": payload["leave_type_name"],
                    "default_annual_days": payload["annual_days"],
                }
            ),
        )
        message = (
            f"Created leave type {data['name']} with "
            f"{data['default_annual_days']} days per year."
        )
    elif tool == "create_announcement":
        create_payload = {
            "title": payload.get("title"),
            "body": payload.get("body"),
            "is_active": payload.get("announcement_is_active", True),
        }
        data = await create_announcement(
            state, db, AnnouncementCreate.model_validate(create_payload)
        )
        message = f"Published announcement {data['title']}."
    elif tool == "delete_announcement":
        data = await delete_announcement(state, db, _target_id(state, "announcement_id"))
        message = f"Deleted announcement {data['title']}."
    elif tool == "update_announcement":
        announcement_id = _target_id(state, "announcement_id")
        update_data = payload.get("updates", payload)
        if isinstance(update_data, dict):
            update_data = {k: v for k, v in update_data.items() if k != "announcement_id"}
        data = await update_announcement(
            state, db, announcement_id, AnnouncementUpdate.model_validate(update_data)
        )
        message = f"Updated announcement {data['title']}."
    elif tool == "create_holiday":
        data = await create_holiday(state, db, HolidayCreate.model_validate(payload))
        message = f"Created holiday {data['name']} on {data['date']}."
    elif tool == "delete_holiday":
        data = await delete_holiday(state, db, _target_id(state, "holiday_id"))
        message = f"Deleted holiday {data['name']}."
    elif tool == "upload_policy":
        data = await complete_policy_upload(
            state, db, _target_id(state, "document_id")
        )
        message = f"Uploaded and indexed policy {data['title']}."
    elif tool == "delete_policy":
        data = await delete_policy(state, db, _target_id(state, "document_id"))
        message = f"Deleted policy {data['title']} and its indexed content."
    elif tool == "update_policy":
        data = await update_policy(
            state,
            db,
            _target_id(state, "document_id"),
            title=str(payload["policy_title"]),
            category=str(payload["policy_category"]),
        )
        message = f"Updated policy {data['title']}."
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
    elif tool == "correct_attendance":
        attendance_date = date.fromisoformat(str(payload["date"]))
        data = await correct_employee_attendance(
            state,
            db,
            _target_id(state, "employee_id"),
            attendance_date,
            AttendanceDateCorrection.model_validate(
                {
                    "status": payload["status"],
                    "correction_reason": payload["correction_reason"],
                }
            ),
        )
        message = (
            f"Corrected {data['employee']}'s attendance for {data['date']} "
            f"to {str(data['status']).replace('_', ' ')}."
        )
    elif tool == "delete_department":
        data = await delete_department(state, db, _target_id(state, "department_id"))
        message = f"Deleted department {data['name']}."
    elif tool == "create_designation":
        data = await create_designation(state, db, DesignationCreate.model_validate(payload))
        message = f"Created designation {data['title']} in {data['department']}."
    elif tool == "delete_designation":
        data = await delete_designation(state, db, _target_id(state, "designation_id"))
        message = f"Deleted designation {data['title']}."
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
    # Explicit action commands are detected even while a workflow is active:
    # repeating the same command starts a clean flow, while a different action
    # requires switch confirmation. Plain slot answers never match a tool and
    # continue the current flow normally.
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
                    "message": (
                        f"I could not identify the requested {_assistant_role_name(state)} "
                        "Assistant action."
                    ),
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

    if tool in {"approve_leave", "reject_leave"}:
        leave_resolution_error = await _resolve_pending_leave_reference(
            tool, payload, state["message"], state, db
        )
        if leave_resolution_error:
            result, next_pending = _pending_result(
                tool,
                payload,
                "slots",
                leave_resolution_error,
                "request_id",
                previous=pending,
            )
            suggestions, _ = await _slot_suggestions(
                tool, "request_id", state, db, payload
            )
            if suggestions:
                result.setdefault("data", {})["suggestions"] = suggestions
            return result, next_pending, sanitized

    if tool in {
        "update_employee",
        "upload_employee_photo",
        "delete_employee",
        "correct_attendance",
    }:
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

    if tool == "update_employee":
        edit_error = await _prepare_employee_edit(payload, db)
        if edit_error:
            missing_edit_field = (
                "employee_id"
                if not payload.get("employee_id")
                else "update_field"
                if not payload.get("update_field")
                else "update_value"
            )
            result, next_pending = _pending_result(
                tool,
                payload,
                "slots",
                edit_error,
                missing_edit_field,
                previous=pending,
            )
            suggestions, _ = await _slot_suggestions(
                tool, missing_edit_field, state, db, payload
            )
            if suggestions:
                result.setdefault("data", {})["suggestions"] = suggestions
            return result, next_pending, sanitized

    if tool == "update_announcement":
        await _prepare_announcement_edit(payload, db)
    if tool == "update_policy":
        await _prepare_policy_edit(payload, db)

    missing = _missing_field(tool, payload)
    if missing:
        prompt = FIELD_PROMPTS[missing]
        if tool == "update_employee" and missing == "update_value":
            label = EMPLOYEE_UPDATE_FIELD_LABELS.get(
                str(payload.get("update_field", "")), "selected field"
            )
            prompt = (
                f"Current {label.lower()}: "
                f"{payload.get('_current_update_display', 'Not set')}\n"
                "Enter the new value. For an optional field, type 'clear' to remove it."
            )
        elif tool == "update_announcement":
            current = payload.get(
                f"_original_{missing.removeprefix('announcement_')}"
            )
            if missing == "announcement_title":
                prompt = (
                    f"Current title: {current}\n"
                    "Enter a new title, or reply 'keep' to leave it unchanged."
                )
            elif missing == "announcement_body":
                prompt = (
                    f"Current message: {current}\n"
                    "Enter the new message, or reply 'keep' to leave it unchanged."
                )
            elif missing == "announcement_is_active":
                visibility = "Visible" if current else "Hidden"
                prompt = (
                    f"Current visibility: {visibility}. Choose whether the announcement "
                    "should remain visible or be hidden."
                )
        elif tool == "update_policy":
            current = payload.get(
                f"_original_{missing.removeprefix('policy_')}"
            )
            label = "title" if missing == "policy_title" else "category"
            prompt = (
                f"Current policy {label}: {current}\n"
                f"Enter a new {label}, or reply 'keep' to leave it unchanged."
            )
        suggestions, prompt_override = await _slot_suggestions(
            tool, missing, state, db, payload
        )
        if prompt_override:
            prompt = prompt_override
        result, next_pending = _pending_result(
            tool,
            payload,
            "slots",
            prompt,
            missing,
            previous=pending,
        )
        if suggestions:
            result.setdefault("data", {})["suggestions"] = suggestions
        return result, next_pending, sanitized

    if tool == "update_announcement":
        updates = _announcement_updates(payload)
        if not updates:
            return (
                {
                    "agent": "action",
                    "status": "cancelled",
                    "tool": tool,
                    "message": "No announcement values were changed. Nothing was updated.",
                },
                None,
                sanitized,
            )
        payload["updates"] = updates
    if tool == "update_policy" and all(
        payload.get(field) == payload.get(f"_original_{field.removeprefix('policy_')}")
        for field in ("policy_title", "policy_category")
    ):
        return (
            {
                "agent": "action",
                "status": "cancelled",
                "tool": tool,
                "message": "No policy values were changed. Nothing was updated.",
            },
            None,
            sanitized,
        )

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
