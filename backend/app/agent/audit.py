"""Best-effort, secret-safe audit logging for agent tool attempts."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.flows import TOOL_WORKFLOWS
from app.agent.state import AgentState, AgentToolResult
from app.models.agent_audit import AgentToolAudit


async def audit_tool_result(
    db: AsyncSession, state: AgentState, result: AgentToolResult
) -> None:
    tool = str(result.get("tool", "unknown"))
    spec = TOOL_WORKFLOWS.get(tool)
    # Never persist tool arguments: they can contain passwords, personal data,
    # document text, or prompt-injection strings.
    audit_message = result.get("message", "")
    if tool == "create_employee" and result.get("status") == "success":
        audit_message = "Employee created; temporary credential was not logged."
    entry = AgentToolAudit(
        actor_user_id=state.get("user_id"),
        conversation_id=state.get("conversation_id"),
        agent=result["agent"],
        tool=tool,
        status=result["status"],
        permission=spec.permission if spec else None,
        message=audit_message[:1000],
        metadata_json={"role": str(state.get("role", "unknown"))},
    )
    try:
        db.add(entry)
        await db.commit()
    except Exception:  # noqa: BLE001 - audit failure must not break the user flow
        await db.rollback()
