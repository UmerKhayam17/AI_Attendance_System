from rest_framework.exceptions import ValidationError


def _limit_error(message: str):
    raise ValidationError({"error": message})


def ensure_person_slot(organization):
    from employees.models import Employee

    limit = organization.limits()["people"]
    count = Employee.objects.filter(organization=organization).count()
    if limit is not None and count >= limit:
        _limit_error(
            f"People limit reached ({limit}). Upgrade your plan to add more."
        )


def ensure_branch_slot(organization):
    from organizations.models import Branch

    limit = organization.limits().get("branches")
    if limit is None:
        return
    count = Branch.objects.filter(organization=organization).count()
    if count >= int(limit):
        _limit_error(
            f"Branch limit reached ({limit}). Upgrade your plan to add more locations."
        )


def ensure_camera_slot(organization):
    from recognition.models import Camera

    limit = organization.limits()["cameras"]
    if not limit:
        _limit_error("Your plan does not include CCTV cameras. Upgrade to Starter or Pro.")
    count = Camera.objects.filter(organization=organization).count()
    if count >= limit:
        _limit_error(
            f"Camera limit reached ({limit}). Upgrade your plan to add more cameras."
        )


def ensure_staff_slot(organization):
    from organizations.models import Membership

    limit = organization.limits()["staff"]
    if limit is None:
        return
    count = Membership.objects.filter(
        organization=organization,
        role__in=Membership.STAFF_ROLES,
    ).count()
    pending = organization.invites.filter(
        accepted_at__isnull=True,
        role__in=Membership.STAFF_ROLES,
    ).count()
    if count + pending >= limit:
        _limit_error(
            f"Staff login limit reached ({limit}). Upgrade your plan to invite more users."
        )


def camera_quota(organization) -> int:
    return int(organization.limits()["cameras"] or 0)
