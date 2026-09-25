"""Permission-controlled Action Agent for HRMS mutations."""

import re
import uuid
from typing import Literal

from fastapi import HTTPException
from langgraph.runtime import Runtime
from pydantic import ValidationError

from app.agent.state import AgentRuntimeContext, AgentState, AgentToolResult
from app.agent.tools.write_tools import (
    WriteToolAccessDenied,
    WriteToolConflict,
    approve_leave,
    create_department,
    create_employee,
    delete_employee,
    reject_leave,
    update_employee,
)
from app.schemas.department import DepartmentCreate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate

ActionToolName = Literal[
    "create_employee",
    "update_employee",
    "delete_employee",
    "approve_leave",
    "reject_leave",
    "create_department",
]

UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def select_action_tool(message: str) -> ActionToolName | None:
    normalized = " ".join(message.lower().split())
    patterns: tuple[tuple[str, ActionToolName], ...] = (
        (r"\b(create|add)\b.*\bemployee\b", "create_employee"),
        (r"\b(update|change|edit)\b.*\bemployee\b", "update_employee"),
        (r"\b(delete|remove)\b.*\bemployee\b", "delete_employee"),
        (r"\bapprove\b.*\bleave\b", "approve_leave"),
        (r"\breject\b.*\bleave\b", "reject_leave"),
        (r"\b(create|add)\b.*\bdepartment\b", "create_department"),
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


async def run_action(state: AgentState, db) -> AgentToolResult:
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


async def action_agent_node(
    state: AgentState, runtime: Runtime[AgentRuntimeContext]
) -> dict:
    try:
        result = await run_action(state, runtime.context["db"])
    except WriteToolAccessDenied as exc:
        result = {
            "agent": "action",
            "status": "denied",
            "message": str(exc),
        }
    except (WriteToolConflict, ValidationError, HTTPException) as exc:
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
            "message": detail,
        }
    return {
        "tool_results": [result],
        "route_trace": ["action_agent"],
    }
