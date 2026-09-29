from rest_framework.permissions import BasePermission

from organizations.models import Membership


class IsPlatformAdmin(BasePermission):
    message = "Platform super admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_superuser)


class HasOrganization(BasePermission):
    message = "No organization membership"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        return bool(org and org.is_active)


def roles_allowed(*allowed: str):
    allowed_set = set(allowed)

    class RolePermission(HasOrganization):
        message = "You do not have permission to perform this action"

        def has_permission(self, request, view):
            if not super().has_permission(request, view):
                return False
            role = getattr(request, "role", None)
            if role == Membership.ROLE_OWNER:
                return True
            if role == "api":
                return bool(
                    allowed_set
                    & {
                        Membership.ROLE_OWNER,
                        Membership.ROLE_ADMIN,
                        Membership.ROLE_OPERATOR,
                    }
                )
            return role in allowed_set

    return RolePermission


IsOwner = roles_allowed(Membership.ROLE_OWNER)
IsOwnerOrAdmin = roles_allowed(Membership.ROLE_OWNER, Membership.ROLE_ADMIN)
CanOperate = roles_allowed(
    Membership.ROLE_OWNER,
    Membership.ROLE_ADMIN,
    Membership.ROLE_OPERATOR,
)
CanView = roles_allowed(
    Membership.ROLE_OWNER,
    Membership.ROLE_ADMIN,
    Membership.ROLE_OPERATOR,
    Membership.ROLE_VIEWER,
)
IsPortalUser = roles_allowed(
    Membership.ROLE_EMPLOYEE,
    Membership.ROLE_PARENT,
)
IsStaffOrPortal = roles_allowed(
    Membership.ROLE_OWNER,
    Membership.ROLE_ADMIN,
    Membership.ROLE_OPERATOR,
    Membership.ROLE_VIEWER,
    Membership.ROLE_EMPLOYEE,
    Membership.ROLE_PARENT,
)
