from attendance.models import LeaveRequest, LeaveType
from payroll.models import PayrollPolicy


DEFAULT_TYPES = [
    ("annual", "Annual", True, "annual_leave_days", "annual_leave_paid", 0),
    ("sick", "Sick", True, "sick_leave_days", "sick_leave_paid", 1),
    ("casual", "Casual", True, None, None, 2),
    ("maternity", "Maternity", True, None, None, 3),
    ("emergency", "Emergency", True, None, None, 4),
    ("unpaid", "Unpaid", False, None, None, 5),
    ("other", "Other", False, "other_leave_days", "other_leave_paid", 6),
]


def seed_leave_types(organization, policy=None):
    policy = policy or PayrollPolicy.for_org(organization)
    created = []
    for code, name, paid_default, days_field, paid_field, order in DEFAULT_TYPES:
        defaults = {
            "name": name,
            "paid": bool(getattr(policy, paid_field)) if paid_field else paid_default,
            "entitlement_days": int(getattr(policy, days_field) or 0) if days_field else _default_days(code),
            "is_active": True,
            "sort_order": order,
        }
        if code == LeaveRequest.TYPE_UNPAID:
            defaults["paid"] = False
            defaults["entitlement_days"] = 0
        obj, was_created = LeaveType.objects.get_or_create(
            organization=organization,
            code=code,
            defaults=defaults,
        )
        if was_created:
            created.append(obj)
    return created


def _default_days(code: str) -> int:
    return {"casual": 7, "maternity": 90, "emergency": 2}.get(code, 0)


def active_leave_types(organization):
    seed_leave_types(organization)
    return list(LeaveType.objects.filter(organization=organization, is_active=True))
