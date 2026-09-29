"""Read-only Database Agent backed by permission-aware HRMS tools."""

import re
import uuid
from typing import Literal

from langgraph.runtime import Runtime

from app.agent.audit import audit_tool_result
from app.agent.state import AgentRuntimeContext, AgentState, AgentToolResult
from app.agent.tools.read_tools import (
    ReadToolAccessDenied,
    ReadToolNotFound,
    get_announcements,
    get_attendance_summary,
    get_audit_logs,
    get_employee_details,
    get_holidays,
    get_leave_balance,
    get_leave_history,
    get_org_stats,
    get_policy_catalog,
    list_attendance_records,
    list_departments,
    list_designations,
    list_employees,
    list_leave_requests,
    list_pending_leave_requests,
    list_users,
)
from app.models.leave import LeaveRequestStatus
from app.models.role import RoleEnum

DatabaseToolName = Literal[
    "get_leave_balance",
    "get_attendance_summary",
    "list_attendance_records",
    "list_employees",
    "get_employee_details",
    "get_policy_catalog",
    "get_audit_logs",
    "get_leave_history",
    "list_leave_requests",
    "list_pending_leave_requests",
    "get_holidays",
    "get_announcements",
    "get_org_stats",
    "list_departments",
    "list_designations",
    "list_users",
]

PROFILE_QUERY_PATTERN = re.compile(
    r"\bmy\b.*\b(?:profile|details?|information|name|nmae|employee\s*(?:id|code)|"
    r"email|emial|phone|phoen|mobile|joining|joined|role|department|designation|"
    r"birth|dob|gender|address|city|emergency|account\s*status)\b"
)

EMPLOYEE_LOOKUP_STOP_WORDS = {
    "all",
    "about",
    "details",
    "detail",
    "code",
    "email",
    "employee",
    "employees",
    "find",
    "for",
    "get",
    "give",
    "information",
    "id",
    "me",
    "of",
    "number",
    "phone",
    "profile",
    "show",
    "tell",
    "the",
    "view",
}


def _is_profile_query(message: str) -> bool:
    return bool(PROFILE_QUERY_PATTERN.search(" ".join(message.lower().split())))


def _employee_lookup_terms(message: str) -> set[str]:
    """Return only words that can identify a requested employee."""
    normalized = re.sub(r"[^a-z0-9@._-]+", " ", message.lower())
    return {
        word
        for word in normalized.split()
        if word not in EMPLOYEE_LOOKUP_STOP_WORDS and len(word) > 1
    }


def _is_specific_employee_query(message: str) -> bool:
    normalized = " ".join(message.lower().split())
    if _is_profile_query(normalized):
        return False
    has_employee_word = bool(re.search(r"\bemployees?\b", normalized))
    has_detail_word = bool(re.search(r"\b(details?|profile|information)\b", normalized))
    refers_to_other_domain = bool(
        re.search(
            r"\b(policy|policies|leave|attendance|holiday|department|designation|"
            r"announcement|user|account)\b",
            normalized,
        )
    )
    if not has_employee_word and (not has_detail_word or refers_to_other_domain):
        return False
    return bool(_employee_lookup_terms(normalized)) and bool(
        re.search(r"\b(show|view|find|get|details?|profile|information|about)\b", normalized)
    )


def _assistant_role_name(state: AgentState) -> str:
    role = RoleEnum(state["role"])
    return {
        RoleEnum.ADMIN: "Admin",
        RoleEnum.HR: "HR",
        RoleEnum.EMPLOYEE: "Employee",
    }[role]


def select_database_tool(message: str) -> DatabaseToolName | None:
    normalized = " ".join(message.lower().split())
    if _is_profile_query(normalized):
        return "get_employee_details"
    if "audit" in normalized and any(
        word in normalized for word in ("show", "view", "list", "log", "logs")
    ):
        return "get_audit_logs"
    if "announcement" in normalized:
        return "get_announcements"
    if "holiday" in normalized:
        return "get_holidays"
    if "leave" in normalized and re.search(r"\b(my|mine|own)\b", normalized):
        return "get_leave_history"
    if "leave" in normalized and "pending" in normalized:
        return "list_pending_leave_requests"
    if re.search(
        r"\b(leave approvals?|approval leaves?|employee leaves?|hr leaves?|approvals?)\b",
        normalized,
    ):
        return "list_pending_leave_requests"
    if re.search(
        r"\b(show|view|list|get|see|check|review)\b.*\b(leaves?|leave requests?)\b",
        normalized,
    ):
        return "list_leave_requests"
    if "leave" in normalized and any(word in normalized for word in ("manage", "review")):
        return "list_pending_leave_requests"
    if "leave" in normalized and any(
        word in normalized for word in ("history", "requests", "approved", "rejected")
    ):
        return "get_leave_history"
    if re.search(
        r"\b(how many|number of|total|count|list|show|available)\b.*\bpolic(?:y|ie|ies)\b",
        normalized,
    ):
        return "get_policy_catalog"
    if "attendance" in normalized and re.search(r"\b(my|mine|own)\b", normalized):
        return "get_attendance_summary"
    if "attendance" in normalized:
        return "list_attendance_records"
    if "leave" in normalized and any(
        word in normalized for word in ("balance", "remaining", "how many", "left")
    ):
        return "get_leave_balance"
    if "dashboard" in normalized or (
        "organization" in normalized
        and any(word in normalized for word in ("stat", "overview", "summary"))
    ):
        return "get_org_stats"
    entities = ("department", "designation", "employee", "user", "account")
    if sum(1 for entity in entities if entity in normalized) >= 2:
        return "get_org_stats"
    if _is_specific_employee_query(normalized):
        return "get_employee_details"
    if re.search(r"\b(list|show|find|get|how many|number of|total|count)\b.*\bemployees?\b", normalized):
        return "list_employees"
    if "department" in normalized:
        return "list_departments"
    if "designation" in normalized:
        return "list_designations"
    if re.search(r"\b(users?|accounts?)\b", normalized):
        return "list_users"
    if any(term in normalized for term in ("employee details", "my profile")):
        return "get_employee_details"
    return None


def _profile_response(
    message: str, profile: dict[str, object]
) -> tuple[str, dict[str, object]]:
    """Return only the requested profile fields, or the complete safe profile."""
    normalized = " ".join(message.lower().split())
    labels = {
        "employee_id": "Employee ID",
        "employee_code": "Employee code",
        "full_name": "Name",
        "email": "Email",
        "role": "Role",
        "account_status": "Account status",
        "phone": "Phone",
        "date_of_joining": "Joining date",
        "date_of_birth": "Date of birth",
        "gender": "Gender",
        "address": "Address",
        "city": "City",
        "emergency_contact": "Emergency contact",
        "department": "Department",
        "designation": "Designation",
    }
    terms = {
        "employee_id": ("employee id", "my id"),
        "employee_code": ("employee code",),
        "full_name": ("name", "nmae"),
        "email": ("email", "emial"),
        "role": ("role",),
        "account_status": ("account status", "active", "inactive"),
        "phone": ("phone", "phoen", "mobile"),
        "date_of_joining": ("joining", "joined"),
        "date_of_birth": ("date of birth", "birth date", "dob"),
        "gender": ("gender",),
        "address": ("address",),
        "city": ("city",),
        "emergency_contact": ("emergency",),
        "department": ("department",),
        "designation": ("designation", "job title"),
    }
    show_all = any(
        term in normalized
        for term in ("profile", "details", "information", "all")
    )
    selected_keys = list(labels) if show_all else [
        key
        for key, keywords in terms.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    if not selected_keys:
        selected_keys = ["full_name", "employee_code", "department", "designation"]
    selected = {key: profile.get(key) for key in selected_keys}
    parts = [
        f"{labels[key]}: {selected[key] if selected[key] not in (None, '') else 'not provided'}"
        for key in selected_keys
    ]
    return "; ".join(parts) + ".", selected


def _employee_id_from_message(message: str) -> uuid.UUID | None:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
        message,
    )
    return uuid.UUID(match.group()) if match else None


def _matching_employees(
    message: str, employees: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Resolve an employee reference without allowing the model to invent an ID."""
    normalized = " ".join(message.lower().split())
    message_digits = re.sub(r"\D", "", message)
    terms = _employee_lookup_terms(message)
    exact: list[dict[str, object]] = []
    partial: list[dict[str, object]] = []
    for employee in employees:
        employee_id = str(employee.get("employee_id") or "").lower()
        code = str(employee.get("employee_code") or "").lower()
        email = str(employee.get("email") or "").lower()
        phone = str(employee.get("phone") or "").lower()
        name = " ".join(str(employee.get("full_name") or "").lower().split())
        phone_digits = re.sub(r"\D", "", phone)
        phone_matches = (
            len(message_digits) >= 7
            and len(phone_digits) >= 7
            and (message_digits in phone_digits or phone_digits in message_digits)
        )
        if phone_matches or any(
            value and value in normalized for value in (employee_id, code, email, name)
        ):
            exact.append(employee)
            continue
        identity_words = set(
            re.findall(r"[a-z0-9@._-]+", f"{name} {code} {email} {phone}")
        )
        if terms and terms <= identity_words:
            partial.append(employee)
    return exact or partial


async def run_database_query(state: AgentState, db) -> AgentToolResult:
    tool = select_database_tool(state["message"])
    if tool is None:
        return {
            "agent": "database",
            "status": "error",
            "tool": "unknown",
            "message": (
                f"I could not identify the requested {_assistant_role_name(state)} "
                "Assistant information request."
            ),
        }

    if tool == "get_announcements":
        records = await get_announcements(state, db)
        data = {"announcements": records}
        message = (
            f"I found {len(records)} active announcement(s)."
            if records
            else "There are no active announcements."
        )
    elif tool == "get_holidays":
        records = await get_holidays(state, db)
        data = {"holidays": records}
        message = (
            f"I found {len(records)} holiday(s) this year."
            if records
            else "No holidays were found for this year."
        )
    elif tool == "list_pending_leave_requests":
        normalized = " ".join(state["message"].lower().split())
        requester_role = (
            RoleEnum.HR
            if re.search(r"\bhr\s+(?:pending\s+)?leaves?\b", normalized)
            else RoleEnum.EMPLOYEE
            if re.search(r"\bemployees?\s+(?:pending\s+)?leaves?\b", normalized)
            else None
        )
        records = await list_pending_leave_requests(
            state, db, requester_role=requester_role
        )
        data = {"leave_requests": records}
        message = (
            f"There are {len(records)} pending leave request(s)."
            if records
            else "There are no pending leave requests."
        )
    elif tool == "list_leave_requests":
        normalized = " ".join(state["message"].lower().split())
        status_filter = next(
            (
                status
                for word, status in (
                    ("approved", LeaveRequestStatus.APPROVED),
                    ("rejected", LeaveRequestStatus.REJECTED),
                    ("cancelled", LeaveRequestStatus.CANCELLED),
                    ("canceled", LeaveRequestStatus.CANCELLED),
                    ("pending", LeaveRequestStatus.PENDING),
                )
                if word in normalized
            ),
            None,
        )
        records = await list_leave_requests(
            state, db, request_status=status_filter
        )
        data = {"leave_requests": records}
        label = f" {status_filter.value}" if status_filter else ""
        message = (
            f"I found {len(records)}{label} employee leave request(s)."
            if records
            else f"No{label} employee leave requests were found."
        )
    elif tool == "get_leave_history":
        records = await get_leave_history(state, db)
        data = {"leave_requests": records}
        message = (
            f"I found {len(records)} leave request(s) in your history."
            if records
            else "You have no leave request history."
        )
    elif tool == "get_audit_logs":
        records = await get_audit_logs(state, db)
        data = {"audits": records}
        message = (
            f"I found {len(records)} recent agent audit records."
            if records
            else "No agent audit records were found."
        )
    elif tool == "get_leave_balance":
        data = await get_leave_balance(state, db)
        balances = data["balances"]
        details = "; ".join(
            f"{item['leave_type_name']}: {item['remaining_days']} of "
            f"{item['total_days']} remaining"
            for item in balances
        )
        message = (
            f"Your {data['year']} leave balances are: {details}."
            if balances
            else f"No leave balances were found for {data['year']}."
        )
    elif tool == "get_attendance_summary":
        data = await get_attendance_summary(state, db)
        message = (
            f"Your attendance summary for {data['year']}-{data['month']:02d}: "
            f"{data['present']} present, {data['late']} late, "
            f"{data['half_day']} half-day, and {data['absent']} absent."
        )
    elif tool == "list_attendance_records":
        records = await list_attendance_records(state, db)
        data = {"attendance_records": records}
        message = (
            f"I found {len(records)} attendance record(s) for the current month."
            if records
            else "No employee attendance records were found for the current month."
        )
    elif tool == "list_employees":
        data = await list_employees(state, db)
        message = (
            f"I found {len(data)} employees. Use the searchable list below to view them."
            if data
            else "No employees were found."
        )
    elif tool == "list_departments":
        records = await list_departments(state, db)
        data = {"departments": records}
        message = f"There are {len(records)} department(s)."
    elif tool == "list_designations":
        records = await list_designations(state, db)
        data = {"designations": records}
        message = f"There are {len(records)} designation(s)."
    elif tool == "list_users":
        records = await list_users(state, db)
        data = {"users": records}
        message = f"There are {len(records)} user account(s)."
    elif tool == "get_org_stats":
        data = await get_org_stats(state, db)
        labels = {
            "total_employees": "employees",
            "departments": "departments",
            "designations": "designations",
            "user_accounts": "user accounts",
            "holidays_this_year": "holidays this year",
            "active_announcements": "active announcements",
            "pending_leave_requests": "pending leave requests",
            "policy_documents": "policy documents",
        }
        parts = [f"{value} {labels[key]}" for key, value in data.items() if key in labels]
        message = (
            f"Organization overview: {', '.join(parts)}."
            if parts
            else "No organization metrics are visible to your role."
        )
    elif tool == "get_policy_catalog":
        data = await get_policy_catalog(state, db)
        policies = data["policies"]
        if policies:
            names = ", ".join(
                f"{item['title']} ({item['category']})" for item in policies[:5]
            )
            remaining = len(policies) - 5
            suffix = f", and {remaining} more" if remaining > 0 else ""
            message = (
                f"There are {data['count']} policy documents available: "
                f"{names}{suffix}."
            )
        else:
            message = "There are no policy documents available yet."
    else:
        employee_id = _employee_id_from_message(state["message"])
        if employee_id is None and not _is_profile_query(state["message"]):
            matches = _matching_employees(
                state["message"], await list_employees(state, db)
            )
            if not matches:
                return {
                    "agent": "database",
                    "status": "error",
                    "tool": tool,
                    "message": "I could not find an employee matching that name, email, code, or ID.",
                }
            if len(matches) > 1:
                return {
                    "agent": "database",
                    "status": "needs_input",
                    "tool": "list_employees",
                    "message": (
                        f"I found {len(matches)} matching employees. Please use the "
                        "employee code or email to identify the correct person."
                    ),
                    "data": matches,
                }
            employee_id = uuid.UUID(str(matches[0]["employee_id"]))
        data = await get_employee_details(state, db, employee_id=employee_id)
        message, data = _profile_response(state["message"], data)
    return {
        "agent": "database",
        "status": "success",
        "tool": tool,
        "message": message,
        "data": data,
    }


async def database_agent_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    selected_tool = select_database_tool(state["message"])
    try:
        result = await run_database_query(state, runtime.context["db"])
    except ReadToolAccessDenied as exc:
        result = {
            "agent": "database",
            "status": "denied",
            "tool": selected_tool or "unknown",
            "message": str(exc),
        }
    except (ReadToolNotFound, ValueError) as exc:
        result = {
            "agent": "database",
            "status": "error",
            "tool": selected_tool or "unknown",
            "message": str(exc),
        }
    await audit_tool_result(runtime.context["db"], state, result)
    return {
        "tool_results": [result],
        "route_trace": ["database_agent"],
    }
