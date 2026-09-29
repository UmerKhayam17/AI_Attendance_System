from datetime import date, time
from types import SimpleNamespace

from django.db.models import Q

FALLBACK_START = time(9, 0)
FALLBACK_LATE = time(9, 30)
FALLBACK_END = time(18, 0)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def is_on_time(local_time: time, start: time, late_after: time) -> bool:
    """Present if check-in falls in [start - 6h, late_after], wrapping midnight."""
    now = _minutes(local_time)
    start_m = _minutes(start)
    late_m = _minutes(late_after)
    early_m = (start_m - 6 * 60) % (24 * 60)
    if early_m <= late_m:
        return early_m <= now <= late_m
    return now >= early_m or now <= late_m


def schedule_for(employee=None, organization=None, on_date: date | None = None):
    org = organization or getattr(employee, "organization", None)
    branch = getattr(employee, "branch", None) if employee is not None else None
    if employee is not None:
        assigned = _assignment_shift(employee, on_date)
        if assigned is not None:
            return assigned
    shift = getattr(employee, "shift", None) if employee is not None else None
    if shift is not None and not getattr(shift, "is_active", True):
        shift = None
    if shift is None and org is not None:
        default = getattr(org, "default_shift", None)
        shift = default(branch) if callable(default) else None
        if shift is None:
            shifts = getattr(org, "shifts", None)
            if shifts is not None:
                qs = shifts.filter(is_active=True)
                if branch is not None:
                    shift = qs.filter(branch=branch, is_default=True).first() or qs.filter(branch=branch).first()
                if shift is None:
                    shift = qs.filter(is_default=True).first() or qs.filter(is_active=True).first()
    if shift is not None:
        return shift
    return SimpleNamespace(
        name="General",
        kind="fixed",
        start_time=getattr(org, "work_start", None) or FALLBACK_START,
        late_after=getattr(org, "late_after", None) or FALLBACK_LATE,
        end_time=FALLBACK_END,
        required_hours=None,
        break_start=None,
        break_end=None,
        second_start=None,
        second_end=None,
        grace_minutes=0,
        early_leave_grace_minutes=15,
        overtime_grace_minutes=15,
        is_default=True,
        is_active=True,
        effective_end=lambda: FALLBACK_END,
    )


def _assignment_shift(employee, on_date: date | None):
    assignments = getattr(employee, "shift_assignments", None)
    if assignments is None:
        return None
    if on_date is None:
        from organizations.localtime import local_date

        on_date = local_date(employee=employee)
    qs = (
        assignments.select_related("shift")
        .filter(start_date__lte=on_date)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on_date))
        .order_by("-start_date", "-id")
    )
    for assignment in qs:
        covers = getattr(assignment, "covers", None)
        if callable(covers) and not covers(on_date):
            continue
        shift = assignment.shift
        if shift is not None and getattr(shift, "is_active", True):
            return shift
    return None
