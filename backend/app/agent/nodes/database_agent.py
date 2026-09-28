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
    get_policy_catalog,
    list_employees,
    list_pending_leave_requests,
)

DatabaseToolName = Literal[
    "get_leave_balance",
    "get_attendance_summary",
    "list_employees",
    "get_employee_details",
    "get_policy_catalog",
    "get_audit_logs",
    "get_leave_history",
    "list_pending_leave_requests",
    "get_holidays",
    "get_announcements",
]


def select_database_tool(message: str) -> DatabaseToolName | None:
    normalized = " ".join(message.lower().split())
    if "audit" in normalized and any(
        word in normalized for word in ("show", "view", "list", "log", "logs")
    ):
        return "get_audit_logs"
    if "announcement" in normalized:
        return "get_announcements"
    if "holiday" in normalized:
        return "get_holidays"
    if "leave" in normalized and "pending" in normalized:
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
    if "attendance" in normalized:
        return "get_attendance_summary"
    if "leave" in normalized and any(
        word in normalized for word in ("balance", "remaining", "how many", "left")
    ):
        return "get_leave_balance"
    if re.search(r"\b(list|show|find|get)\b.*\bemployees\b", normalized):
        return "list_employees"
    if any(term in normalized for term in ("employee details", "my profile")):
        return "get_employee_details"
    return None


def _employee_id_from_message(message: str) -> uuid.UUID | None:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
        message,
    )
    return uuid.UUID(match.group()) if match else None


async def run_database_query(state: AgentState, db) -> AgentToolResult:
    tool = select_database_tool(state["message"])
    if tool is None:
        return {
            "agent": "database",
            "status": "error",
            "tool": "unknown",
            "message": "I could not identify the requested HR information.",
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
        records = await list_pending_leave_requests(state, db)
        data = {"leave_requests": records}
        message = (
            f"There are {len(records)} pending leave request(s)."
            if records
            else "There are no pending leave requests."
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
    elif tool == "list_employees":
        data = await list_employees(state, db)
        message = (
            f"I found {len(data)} employees. Use the searchable list below to view them."
            if data
            else "No employees were found."
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
        data = await get_employee_details(
            state, db, employee_id=_employee_id_from_message(state["message"])
        )
        message = (
            f"{data['full_name']} ({data['employee_code'] or 'no employee code'}), "
            f"department: {data['department'] or 'not assigned'}, "
            f"designation: {data['designation'] or 'not assigned'}."
        )
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
