from app.models.role import RoleEnum

# permission string convention: "<resource>:<action>"
PERMISSIONS: dict[str, set[RoleEnum]] = {
    #employess
    "employee:create": {RoleEnum.ADMIN, RoleEnum.HR},
    "employee:read_all": {RoleEnum.ADMIN, RoleEnum.HR},
    "employee:read_self": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},
    "employee:update": {RoleEnum.ADMIN, RoleEnum.HR},
    "employee:delete": {RoleEnum.ADMIN},

    #departments and designations
    "department:write": {RoleEnum.ADMIN},
    "department:read": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},
    "designation:write": {RoleEnum.ADMIN},
    "designation:read": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},


    #attendance
    "attendance:check_in_out": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},
    "attendance:read_all": {RoleEnum.ADMIN, RoleEnum.HR},
    "attendance:correct": {RoleEnum.ADMIN, RoleEnum.HR},



    #leaves
    "leave:apply": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},
    "leave:approve": {RoleEnum.ADMIN, RoleEnum.HR},
    "leave:policy_write": {RoleEnum.ADMIN},
    "leave:read_all": {RoleEnum.ADMIN, RoleEnum.HR},
    "leave:type_write": {RoleEnum.ADMIN},

    "user:manage": {RoleEnum.ADMIN},
    "audit:read": {RoleEnum.ADMIN},

    # used only for today's RBAC test route
    "demo:hr_only": {RoleEnum.ADMIN, RoleEnum.HR},



    #policy documents
    "policy:write": {RoleEnum.ADMIN, RoleEnum.HR},
    "policy:read": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},


    "holiday:write": {RoleEnum.ADMIN},
    "holiday:read": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},
    "announcement:write": {RoleEnum.ADMIN, RoleEnum.HR},
    "announcement:read": {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.EMPLOYEE},

}


def has_permission(role: RoleEnum, permission: str) -> bool:
    allowed_roles = PERMISSIONS.get(permission)
    if allowed_roles is None:
        return False  # fail closed: unknown permission string = deny, never allow
    return role in allowed_roles