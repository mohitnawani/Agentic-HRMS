from app.core.permissions import has_permission
from app.models.role import RoleEnum
from app.services.leave_service import can_review_leave


def test_self_service_role_hierarchy() -> None:
    for permission in (
        "employee:read_self",
        "leave:apply",
        "attendance:check_in_out",
    ):
        assert has_permission(RoleEnum.EMPLOYEE, permission)
        assert has_permission(RoleEnum.HR, permission)
        assert not has_permission(RoleEnum.ADMIN, permission)


def test_employee_management_hierarchy() -> None:
    assert not has_permission(RoleEnum.EMPLOYEE, "employee:create")
    assert has_permission(RoleEnum.HR, "employee:create")
    assert has_permission(RoleEnum.ADMIN, "employee:create")
    assert not has_permission(RoleEnum.HR, "employee:delete")
    assert has_permission(RoleEnum.ADMIN, "employee:delete")


def test_leave_review_hierarchy() -> None:
    assert can_review_leave(RoleEnum.HR, RoleEnum.EMPLOYEE)
    assert not can_review_leave(RoleEnum.HR, RoleEnum.HR)
    assert can_review_leave(RoleEnum.ADMIN, RoleEnum.EMPLOYEE)
    assert can_review_leave(RoleEnum.ADMIN, RoleEnum.HR)
    assert not can_review_leave(RoleEnum.EMPLOYEE, RoleEnum.EMPLOYEE)
