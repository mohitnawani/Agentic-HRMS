"""Permission-aware, read-only HRMS tools used by the Database Agent."""

import re
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.permissions import has_permission
from app.models.agent_audit import AgentToolAudit
from app.models.announcement import Announcement
from app.models.department import Department
from app.models.designation import Designation
from app.models.document_chunk import DocumentChunk
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.models.leave import LeaveRequest, LeaveRequestStatus, LeaveType
from app.models.policy_document import PolicyDocument
from app.models.role import RoleEnum
from app.models.user import User
from app.rag.summarization import build_extractive_summary
from app.services import attendance_service, leave_service


class ReadToolAccessDenied(PermissionError):
    """The authenticated graph actor is not allowed to read the resource."""


class ReadToolNotFound(LookupError):
    """The requested employee resource does not exist."""


def _actor(state: AgentState) -> tuple[uuid.UUID, RoleEnum]:
    """Read trusted identity only from graph state, never tool arguments."""
    try:
        return uuid.UUID(str(state["user_id"])), RoleEnum(state["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ReadToolAccessDenied("Authenticated user context is missing.") from exc


def _require(role: RoleEnum, permission: str) -> None:
    if not has_permission(role, permission):
        raise ReadToolAccessDenied(
            "Your role does not have permission to access this information."
        )


async def _employee_for_user(db: AsyncSession, user_id: uuid.UUID) -> Employee:
    employee = await db.scalar(select(Employee).where(Employee.user_id == user_id))
    if employee is None:
        raise ReadToolNotFound("No employee profile is linked to your account.")
    return employee


async def get_leave_balance(
    state: AgentState, db: AsyncSession, *, year: int | None = None
) -> dict[str, object]:
    """Return only the authenticated user's leave balances."""
    user_id, role = _actor(state)
    _require(role, "employee:read_self")
    employee = await _employee_for_user(db, user_id)
    selected_year = year or datetime.now(UTC).year
    balances = await leave_service.get_balances(db, employee.id, selected_year)
    return {
        "employee_id": str(employee.id),
        "year": selected_year,
        "balances": [
            {
                **balance,
                "leave_type_id": str(balance["leave_type_id"]),
            }
            for balance in balances
        ],
    }


async def get_attendance_summary(
    state: AgentState,
    db: AsyncSession,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, object]:
    """Return the authenticated user's attendance summary for one month."""
    user_id, role = _actor(state)
    _require(role, "employee:read_self")
    employee = await _employee_for_user(db, user_id)
    today = datetime.now(UTC).date()
    selected_year = year or today.year
    selected_month = month or today.month
    if not 1 <= selected_month <= 12:
        raise ValueError("month must be between 1 and 12")
    summary = await attendance_service.get_monthly_summary(
        db, employee.id, selected_year, selected_month
    )
    return {
        "employee_id": str(employee.id),
        "year": selected_year,
        "month": selected_month,
        **summary,
    }


async def list_employees(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    """List safe employee fields for Admin/HR actors only."""
    _, role = _actor(state)
    _require(role, "employee:read_all")
    statement = (
        select(Employee, User.email, Department.name, Designation.title)
        .join(User, User.id == Employee.user_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .order_by(Employee.first_name, Employee.last_name, Employee.id)
    )
    rows = (await db.execute(statement)).all()
    return [
        {
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "full_name": f"{employee.first_name} {employee.last_name}",
            "email": email,
            "phone": employee.phone,
            "department": department,
            "designation": designation,
        }
        for employee, email, department, designation in rows
    ]


async def list_departments(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "department:read")
    rows = list((await db.scalars(select(Department).order_by(Department.name))).all())
    return [
        {
            "department_id": str(item.id),
            "name": item.name,
            "description": item.description,
        }
        for item in rows
    ]


async def list_designations(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "designation:read")
    rows = (
        await db.execute(
            select(Designation, Department.name)
            .join(Department, Department.id == Designation.department_id)
            .order_by(Department.name, Designation.title)
        )
    ).all()
    return [
        {
            "designation_id": str(item.id),
            "title": item.title,
            "department": department,
        }
        for item, department in rows
    ]


async def list_users(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "user:manage")
    rows = list((await db.scalars(select(User).order_by(User.email))).all())
    return [
        {
            "user_id": str(item.id),
            "email": item.email,
            "role": item.role.value,
            "is_active": item.is_active,
        }
        for item in rows
    ]


async def get_policy_catalog(
    state: AgentState, db: AsyncSession
) -> dict[str, object]:
    """Return policy metadata without exposing storage URLs or document contents."""
    _, role = _actor(state)
    _require(role, "policy:read")
    documents = list(
        (
            await db.scalars(
                select(PolicyDocument).order_by(
                    PolicyDocument.created_at.desc(), PolicyDocument.title
                )
            )
        ).all()
    )
    return {
        "count": len(documents),
        "policies": [
            {
                "document_id": str(document.id),
                "title": document.title,
                "category": document.category,
                "version": document.version,
                "summary": document.summary,
                "uploaded_at": document.created_at.isoformat(),
            }
            for document in documents
        ],
    }


async def get_policy_summaries(
    state: AgentState, db: AsyncSession, query: str
) -> dict[str, object]:
    """Select policy summaries by title/category without regenerating them."""
    _, role = _actor(state)
    _require(role, "policy:read")
    documents = list(
        (
            await db.scalars(
                select(PolicyDocument).order_by(PolicyDocument.title)
            )
        ).all()
    )
    if not documents:
        return {"count": 0, "summaries": [], "selection_required": False}

    normalized = " ".join(query.lower().split())
    all_requested = bool(re.search(r"\b(all|each|every)\b", normalized))
    ignored = {
        "a", "about", "an", "give", "me", "of", "overview", "please",
        "policy", "policies", "summarise", "summarize", "summary", "the",
    }
    query_tokens = {
        token for token in re.findall(r"[a-z0-9]+", normalized) if token not in ignored
    }
    selected = documents if all_requested else []
    if not selected and query_tokens:
        scored = []
        for document in documents:
            searchable = set(
                re.findall(
                    r"[a-z0-9]+", f"{document.title} {document.category}".lower()
                )
            )
            scored.append((len(query_tokens & searchable), document))
        best_score = max(score for score, _ in scored)
        if best_score:
            selected = [document for score, document in scored if score == best_score]
    if not selected and len(documents) == 1:
        selected = documents
    if not selected:
        return {
            "count": 0,
            "summaries": [],
            "selection_required": True,
            "policies": [
                {
                    "document_id": str(document.id),
                    "title": document.title,
                    "category": document.category,
                }
                for document in documents
            ],
        }

    summaries = []
    for document in selected[:10]:
        summary = (document.summary or "").strip()
        if not summary:
            chunk_texts = list(
                (
                    await db.scalars(
                        select(DocumentChunk.content)
                        .where(DocumentChunk.document_id == document.id)
                        .order_by(DocumentChunk.chunk_index)
                    )
                ).all()
            )
            summary = build_extractive_summary(chunk_texts)
        summaries.append(
            {
                "document_id": str(document.id),
                "title": document.title,
                "category": document.category,
                "version": document.version,
                "summary": summary or "No readable summary is available.",
            }
        )
    return {
        "count": len(summaries),
        "summaries": summaries,
        "selection_required": False,
    }


async def get_employee_details(
    state: AgentState,
    db: AsyncSession,
    *,
    employee_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Return safe details, restricting employees to their own profile."""
    user_id, role = _actor(state)
    if employee_id is None:
        actor_employee = await _employee_for_user(db, user_id)
        target_id = actor_employee.id
        _require(role, "employee:read_self")
    elif has_permission(role, "employee:read_all"):
        target_id = employee_id
    else:
        actor_employee = await _employee_for_user(db, user_id)
        if employee_id != actor_employee.id:
            raise ReadToolAccessDenied(
                "Your role does not have permission to access this information."
            )
        target_id = employee_id
        _require(role, "employee:read_self")

    statement = (
        select(
            Employee,
            User.email,
            User.role,
            User.is_active,
            Department.name,
            Designation.title,
        )
        .join(User, User.id == Employee.user_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .where(Employee.id == target_id)
    )
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise ReadToolNotFound("Employee not found.")
    employee, email, target_role, is_active, department, designation = row
    return {
        "employee_id": str(employee.id),
        "employee_code": employee.employee_code,
        "full_name": f"{employee.first_name} {employee.last_name}",
        "email": email,
        "role": target_role.value,
        "account_status": "active" if is_active else "inactive",
        "phone": employee.phone,
        "date_of_joining": employee.date_of_joining.isoformat(),
        "date_of_birth": (
            employee.date_of_birth.isoformat() if employee.date_of_birth else None
        ),
        "gender": employee.gender,
        "address": employee.address,
        "city": employee.city,
        "emergency_contact": employee.emergency_contact,
        "department": department,
        "designation": designation,
    }


async def get_audit_logs(
    state: AgentState, db: AsyncSession, *, limit: int = 50
) -> list[dict[str, object]]:
    """Return recent secret-safe agent audit records to administrators."""
    _, role = _actor(state)
    _require(role, "audit:read")
    records = list(
        (
            await db.scalars(
                select(AgentToolAudit)
                .order_by(AgentToolAudit.created_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        ).all()
    )
    return [
        {
            "audit_id": str(record.id),
            "actor_user_id": (
                str(record.actor_user_id) if record.actor_user_id else None
            ),
            "agent": record.agent,
            "tool": record.tool,
            "status": record.status,
            "permission": record.permission,
            "created_at": record.created_at.isoformat(),
        }
        for record in records
    ]


async def get_leave_history(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    user_id, role = _actor(state)
    _require(role, "leave:apply")
    employee = await _employee_for_user(db, user_id)
    rows = (
        await db.execute(
            select(LeaveRequest, LeaveType)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .where(LeaveRequest.employee_id == employee.id)
            .order_by(LeaveRequest.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        {
            "request_id": str(request.id),
            "leave_type": leave_type.name,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "reason": request.reason,
            "status": request.status.value,
        }
        for request, leave_type in rows
    ]


async def list_pending_leave_requests(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "leave:read_all")
    rows = (
        await db.execute(
            select(LeaveRequest, LeaveType, Employee)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .where(LeaveRequest.status == LeaveRequestStatus.PENDING)
            .order_by(LeaveRequest.created_at)
        )
    ).all()
    return [
        {
            "request_id": str(request.id),
            "employee_id": str(employee.id),
            "employee": f"{employee.first_name} {employee.last_name}",
            "leave_type": leave_type.name,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "reason": request.reason,
        }
        for request, leave_type, employee in rows
    ]


async def get_holidays(
    state: AgentState, db: AsyncSession, *, year: int | None = None
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "holiday:read")
    selected_year = year or datetime.now(UTC).year
    rows = list(
        (
            await db.scalars(
                select(Holiday)
                .where(
                    Holiday.date >= date(selected_year, 1, 1),
                    Holiday.date < date(selected_year + 1, 1, 1),
                )
                .order_by(Holiday.date)
            )
        ).all()
    )
    return [
        {"holiday_id": str(item.id), "name": item.name, "date": item.date.isoformat()}
        for item in rows
    ]


async def get_announcements(
    state: AgentState, db: AsyncSession
) -> list[dict[str, object]]:
    _, role = _actor(state)
    _require(role, "announcement:read")
    statement = select(Announcement).where(Announcement.is_active.is_(True))
    rows = list(
        (await db.scalars(statement.order_by(Announcement.created_at.desc()).limit(20))).all()
    )
    return [
        {
            "announcement_id": str(item.id),
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at.isoformat(),
        }
        for item in rows
    ]


async def get_org_stats(state: AgentState, db: AsyncSession) -> dict[str, object]:
    """Organization-wide headcounts for dashboard-style questions.

    Each metric is gated by its own read permission, so the result only ever
    contains what the actor's role may see — an employee gets department and
    holiday counts but never user accounts or pending approvals.
    """
    _, role = _actor(state)
    stats: dict[str, object] = {}

    async def _try(key: str, permission: str, query) -> None:
        try:
            _require(role, permission)
        except ReadToolAccessDenied:
            return
        result = await db.execute(query)
        stats[key] = int(result.scalar_one())

    await _try("total_employees", "employee:read_all", select(func.count()).select_from(Employee))
    await _try("departments", "department:read", select(func.count()).select_from(Department))
    await _try("designations", "designation:read", select(func.count()).select_from(Designation))
    await _try("user_accounts", "user:manage", select(func.count()).select_from(User))
    await _try(
        "holidays_this_year",
        "holiday:read",
        select(func.count())
        .select_from(Holiday)
        .where(
            Holiday.date >= date(datetime.now(UTC).year, 1, 1),
            Holiday.date < date(datetime.now(UTC).year + 1, 1, 1),
        ),
    )
    await _try(
        "active_announcements",
        "announcement:read",
        select(func.count()).select_from(Announcement).where(Announcement.is_active.is_(True)),
    )
    await _try(
        "pending_leave_requests",
        "leave:read_all",
        select(func.count())
        .select_from(LeaveRequest)
        .where(LeaveRequest.status == LeaveRequestStatus.PENDING),
    )
    await _try("policy_documents", "policy:read", select(func.count()).select_from(PolicyDocument))
    return stats
