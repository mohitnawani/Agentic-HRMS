import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.action_agent import run_action, select_action_tool
from app.agent.state import AgentState
from app.agent.tools.write_tools import WriteToolAccessDenied, delete_employee, update_announcement
from app.db.session import async_session
from app.models.announcement import Announcement
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import RoleEnum
from app.models.user import User


async def create_actor(
    db: AsyncSession, role: RoleEnum, label: str
) -> tuple[User, Employee]:
    user = User(
        id=uuid.uuid4(),
        email=f"{label}_{uuid.uuid4().hex}@test.local",
        hashed_password="unused",
        role=role,
    )
    db.add(user)
    await db.flush()
    employee = Employee(
        id=uuid.uuid4(),
        user_id=user.id,
        first_name=label.title(),
        last_name="Tester",
        date_of_joining=datetime.now(UTC).date(),
    )
    db.add(employee)
    await db.flush()
    return user, employee


def state_for(user: User, message: str, **parameters: object) -> AgentState:
    return {
        "user_id": user.id,
        "role": user.role,
        "message": message,
        "action_payload": parameters,
    }


@pytest.mark.asyncio
async def test_employee_delete_is_denied_without_database_write():
    async with async_session() as db:
        actor, _ = await create_actor(db, RoleEnum.EMPLOYEE, "denied_actor")
        target_user, target = await create_actor(db, RoleEnum.EMPLOYEE, "denied_target")

        with pytest.raises(WriteToolAccessDenied):
            await delete_employee(
                state_for(actor, f"Delete employee {target.id}"), db, target.id
            )

        assert await db.get(Employee, target.id) is not None
        assert (await db.get(User, target_user.id)).is_active is True
        await db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [RoleEnum.HR, RoleEnum.ADMIN])
async def test_hr_and_admin_can_delete_employee(role):
    async with async_session() as db:
        actor, actor_employee = await create_actor(db, role, f"{role.value}_actor")
        target_user, target = await create_actor(
            db, RoleEnum.EMPLOYEE, f"{role.value}_target"
        )
        actor_user_id = actor.id
        actor_employee_id = actor_employee.id
        target_user_id = target_user.id
        target_employee_id = target.id
        await db.commit()

        result = await delete_employee(
            state_for(actor, f"Delete employee {target_employee_id}"),
            db,
            target_employee_id,
        )

        assert result == {"employee_id": str(target_employee_id), "deleted": True}
        assert await db.get(Employee, target_employee_id) is None
        assert (await db.get(User, target_user_id)).is_active is False

        await db.execute(delete(Employee).where(Employee.id == actor_employee_id))
        await db.execute(
            delete(User).where(User.id.in_([actor_user_id, target_user_id]))
        )
        await db.commit()


@pytest.mark.asyncio
async def test_database_role_prevents_spoofed_admin_state():
    async with async_session() as db:
        actor, _ = await create_actor(db, RoleEnum.EMPLOYEE, "spoofed_actor")
        _, target = await create_actor(db, RoleEnum.EMPLOYEE, "spoofed_target")
        spoofed_state: AgentState = {
            "user_id": actor.id,
            "role": RoleEnum.ADMIN,
            "message": f"Delete employee {target.id}",
        }

        with pytest.raises(WriteToolAccessDenied):
            await delete_employee(spoofed_state, db, target.id)

        assert await db.get(Employee, target.id) is not None
        await db.rollback()


@pytest.mark.asyncio
async def test_only_admin_can_create_department():
    department_name = f"Agent Department {uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        employee, _ = await create_actor(db, RoleEnum.EMPLOYEE, "department_denied")
        with pytest.raises(WriteToolAccessDenied):
            await run_action(
                state_for(
                    employee,
                    f"Create department {department_name}",
                    name=department_name,
                ),
                db,
            )
        assert (
            await db.scalar(
                select(Department).where(Department.name == department_name)
            )
            is None
        )
        await db.rollback()

    async with async_session() as db:
        admin, admin_employee = await create_actor(
            db, RoleEnum.ADMIN, "department_admin"
        )
        admin_user_id = admin.id
        admin_employee_id = admin_employee.id
        await db.commit()

        created = await run_action(
            state_for(
                admin,
                f"Create department {department_name}",
                name=department_name,
                description="Created through the Action Agent",
            ),
            db,
        )
        department_id = uuid.UUID(created["data"]["department_id"])
        assert created["status"] == "success"
        assert (await db.get(Department, department_id)).name == department_name

        await db.execute(delete(Department).where(Department.id == department_id))
        await db.execute(delete(Employee).where(Employee.id == admin_employee_id))
        await db.execute(delete(User).where(User.id == admin_user_id))
        await db.commit()


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Create a new employee", "create_employee"),
        ("Update employee details", "update_employee"),
        ("Delete employee account", "delete_employee"),
        ("Approve this leave request", "approve_leave"),
        ("Reject this leave request", "reject_leave"),
        ("Create a department", "create_department"),
        ("Update announcement Holiday Party", "update_announcement"),
        ("Change the announcement about parking", "update_announcement"),
        ("Edit announcement Diwali holidays", "update_announcement"),
    ],
)
def test_all_day18_actions_are_selectable(message, expected):
    assert select_action_tool(message) == expected


@pytest.mark.asyncio
async def test_hr_can_update_announcement_through_assistant():
    async with async_session() as db:
        actor, actor_employee = await create_actor(db, RoleEnum.HR, "ann_hr")
        announcement = Announcement(
            title="Holiday Party",
            body="Old details",
            created_by=actor.id,
            is_active=True,
        )
        db.add(announcement)
        await db.commit()
        announcement_id = announcement.id

        result = await run_action(
            state_for(
                actor,
                "Update announcement Holiday Party",
                announcement_id=str(announcement_id),
                updates={"title": "Holiday Party Updated", "body": "New details"},
            ),
            db,
        )

        assert result["status"] == "success"
        assert result["tool"] == "update_announcement"
        refreshed = await db.get(Announcement, announcement_id)
        assert refreshed.title == "Holiday Party Updated"
        assert refreshed.body == "New details"

        await db.delete(refreshed)
        await db.execute(delete(Employee).where(Employee.id == actor_employee.id))
        await db.execute(delete(User).where(User.id == actor.id))
        await db.commit()


@pytest.mark.asyncio
async def test_admin_can_toggle_announcement_visibility_through_assistant():
    async with async_session() as db:
        actor, actor_employee = await create_actor(db, RoleEnum.ADMIN, "ann_admin")
        announcement = Announcement(
            title="Parking Notice",
            body="Lot closed",
            created_by=actor.id,
            is_active=True,
        )
        db.add(announcement)
        await db.commit()
        announcement_id = announcement.id

        result = await run_action(
            state_for(
                actor,
                "Update announcement Parking Notice",
                announcement_id=str(announcement_id),
                updates={"is_active": False},
            ),
            db,
        )

        assert result["status"] == "success"
        assert (await db.get(Announcement, announcement_id)).is_active is False

        await db.delete(await db.get(Announcement, announcement_id))
        await db.execute(delete(Employee).where(Employee.id == actor_employee.id))
        await db.execute(delete(User).where(User.id == actor.id))
        await db.commit()


@pytest.mark.asyncio
async def test_employee_update_announcement_is_denied_without_database_write():
    async with async_session() as db:
        actor, actor_employee = await create_actor(db, RoleEnum.EMPLOYEE, "ann_denied")
        announcement = Announcement(
            title="Secret Meeting",
            body="Original",
            created_by=actor.id,
            is_active=True,
        )
        db.add(announcement)
        await db.flush()
        announcement_id = announcement.id
        original_title = announcement.title

        with pytest.raises(WriteToolAccessDenied):
            await update_announcement(
                state_for(actor, "Update announcement Secret Meeting"),
                db,
                announcement_id,
                {"title": "Hacked"},  # type: ignore[arg-type]
            )

        assert (await db.get(Announcement, announcement_id)).title == original_title
        await db.rollback()
