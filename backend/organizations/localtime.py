"""Resolve local date/time from branch or organization timezone."""
from __future__ import annotations

from datetime import date, datetime, time, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_tz


def zone_for(*, employee=None, organization=None, branch=None) -> tzinfo:
    if branch is None and employee is not None:
        branch = getattr(employee, "branch", None)
    tz_name = getattr(branch, "timezone", None) if branch is not None else None
    if not tz_name:
        if organization is None and employee is not None:
            organization = getattr(employee, "organization", None)
        tz_name = getattr(organization, "timezone", None) if organization is not None else None
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            pass
    return dj_tz.get_current_timezone()


def as_local(value: datetime, *, employee=None, organization=None, branch=None) -> datetime:
    if value is None:
        return value
    if dj_tz.is_naive(value):
        value = dj_tz.make_aware(value, dj_tz.get_current_timezone())
    return value.astimezone(zone_for(employee=employee, organization=organization, branch=branch))


def local_now(*, employee=None, organization=None, branch=None, now: datetime | None = None) -> datetime:
    now = now or dj_tz.now()
    return as_local(now, employee=employee, organization=organization, branch=branch)


def local_date(*, employee=None, organization=None, branch=None, now: datetime | None = None) -> date:
    return local_now(employee=employee, organization=organization, branch=branch, now=now).date()


def local_time(*, employee=None, organization=None, branch=None, now: datetime | None = None) -> time:
    return local_now(employee=employee, organization=organization, branch=branch, now=now).time()
