"""Working-day helpers: weekends, holidays, approved leave."""
from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q

from attendance.models import Holiday, LeaveRequest


def weekend_days(organization, branch=None) -> set[int]:
    raw = None
    if branch is not None:
        raw = getattr(branch, "weekend_days", None)
    if not raw:
        raw = getattr(organization, "weekend_days", None) or [5, 6]
    days = set()
    for value in raw:
        try:
            n = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= n <= 6:
            days.add(n)
    return days or {5, 6}


def is_weekend(organization, day: date, branch=None) -> bool:
    return day.weekday() in weekend_days(organization, branch=branch)


def holiday_on(organization, day: date, branch=None):
    qs = Holiday.objects.filter(organization=organization)
    if branch is not None:
        scoped = qs.filter(Q(branch=branch) | Q(branch__isnull=True))
        exact = scoped.filter(date=day, branch=branch).first() or scoped.filter(date=day, branch__isnull=True).first()
        if exact:
            return exact
        yearly = scoped.filter(repeats_yearly=True, date__month=day.month, date__day=day.day)
        return yearly.filter(branch=branch).first() or yearly.filter(branch__isnull=True).first()
    exact = qs.filter(date=day, branch__isnull=True).first() or qs.filter(date=day).first()
    if exact:
        return exact
    return qs.filter(
        repeats_yearly=True,
        date__month=day.month,
        date__day=day.day,
        branch__isnull=True,
    ).first()


def leave_on(employee, day: date):
    return (
        LeaveRequest.objects.filter(
            employee=employee,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=day,
            end_date__gte=day,
        )
        .order_by("-id")
        .first()
    )


def is_non_working(organization, day: date, branch=None) -> tuple[bool, str]:
    hol = holiday_on(organization, day, branch=branch)
    if hol:
        return True, hol.name or "Holiday"
    if is_weekend(organization, day, branch=branch):
        return True, "Weekend"
    return False, ""


def expected_employees(organization, day: date, employees):
    """Active people who should be at work (not weekend/holiday/approved leave)."""
    expected = []
    for emp in employees:
        branch = getattr(emp, "branch", None)
        off, _reason = is_non_working(organization, day, branch=branch)
        if off:
            continue
        if leave_on(emp, day):
            continue
        expected.append(emp)
    return expected


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)
