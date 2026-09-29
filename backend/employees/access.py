from employees.models import Employee
from organizations.models import Membership


def portal_employees_qs(user, organization, role: str | None = None):
    if organization is None or user is None:
        return Employee.objects.none()
    if role == Membership.ROLE_EMPLOYEE:
        return Employee.objects.filter(organization=organization, user=user, is_active=True)
    if role == Membership.ROLE_PARENT:
        return Employee.objects.filter(
            organization=organization,
            parent_links__user=user,
            is_active=True,
        ).distinct()
    return Employee.objects.none()


def can_access_employee(user, organization, role, employee: Employee) -> bool:
    if not employee or employee.organization_id != getattr(organization, "id", None):
        return False
    if Membership.is_staff_role(role) or role == Membership.ROLE_OWNER:
        return True
    return portal_employees_qs(user, organization, role).filter(pk=employee.pk).exists()
