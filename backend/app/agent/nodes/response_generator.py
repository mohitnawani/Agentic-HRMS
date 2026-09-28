"""Final response node shared by every supervisor route."""

import re

from app.agent.state import AgentState
from app.models.role import RoleEnum


def _general_response(state: AgentState) -> str:
    message = " ".join(state["message"].lower().split())
    role = RoleEnum(state["role"])
    if message in {"yes", "y", "confirm", "no", "n"}:
        return "There is no action waiting for confirmation. What would you like to do?"
    if re.fullmatch(r"(hi|hello|hey|thanks|thank you|bye)[.! ]*", message):
        return "Hello. Ask what I can do to see the HRMS actions available to your role."
    if re.search(r"\b(help|what can you do|options)\b", message):
        if role == RoleEnum.EMPLOYEE:
            return (
                "I can help with your profile, leave, attendance, holidays, "
                "announcements, and company policies."
            )
        if role == RoleEnum.HR:
            return (
                "I can help with your own profile, leave and attendance; manage "
                "employees; review employee leave and attendance; and manage "
                "announcements and policies."
            )
        return (
            "I can manage employees, employee and HR leave approvals, policies, "
            "announcements, holidays, departments, designations, users, "
            "organization statistics, and audit logs."
        )
    if not re.search(r"[a-z0-9]", message):
        return "I didn't catch that. Ask about leave, attendance, policies, or your profile."
    return (
        "I can only help with HRMS topics such as leave, attendance, employees, "
        "announcements, and company policies."
    )


def response_generator_node(state: AgentState) -> dict:
    results = state.get("tool_results", [])
    answer = results[-1]["message"] if results else _general_response(state)
    pending = state.get("pending_action")
    if pending and results and results[-1].get("agent") != "action":
        tool = str(pending.get("tool", "action")).replace("_", " ")
        if pending.get("stage") == "confirmation":
            reminder = f"Your {tool} is still waiting for confirmation. Confirm or cancel?"
        else:
            field = str(pending.get("missing_field", "the requested detail")).replace(
                "_", " "
            )
            reminder = f"To continue {tool}, please provide {field}."
        answer = f"{answer}\n\n{reminder}"
    return {"final_answer": answer, "route_trace": ["response_generator"]}
