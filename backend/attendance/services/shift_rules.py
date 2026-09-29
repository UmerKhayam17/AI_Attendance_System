"""Checkout HR rules: half-day, early leave, overtime from shift end_time."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from attendance.models import AttendanceRecord
from organizations.localtime import as_local
from organizations.shifts import schedule_for

EARLY_LEAVE_GRACE_MIN = 15
OVERTIME_GRACE_MIN = 15


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def shift_length_minutes(start: time, end: time) -> int:
    s, e = _minutes(start), _minutes(end)
    delta = e - s
    if delta <= 0:
        delta += 24 * 60
    return delta


def minutes_after(local: time, end: time) -> int:
    """Positive if local is after end, wrapping midnight."""
    diff = _minutes(local) - _minutes(end)
    if diff < -12 * 60:
        diff += 24 * 60
    if diff > 12 * 60:
        diff -= 24 * 60
    return diff


def _grace(schedule, name: str, fallback: int) -> int:
    value = getattr(schedule, name, None)
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def apply_checkout_rules(record: AttendanceRecord, employee=None, now: datetime | None = None) -> AttendanceRecord:
    if record.check_in is None or record.check_out is None:
        return record
    now = now or record.check_out
    organization = getattr(employee, "organization", None) or getattr(record.employee, "organization", None)
    employee = employee or record.employee
    schedule = schedule_for(employee=employee, organization=organization, on_date=record.date)
    kind = getattr(schedule, "kind", "fixed")

    worked = record.check_out - record.check_in
    if worked < timedelta(0):
        worked = timedelta(0)

    required = getattr(schedule, "required_hours", None)
    if kind == "flexible" and required:
        shift_min = int(Decimal(str(required)) * 60)
    else:
        shift_min = shift_length_minutes(schedule.start_time, schedule.end_time)
        second_start = getattr(schedule, "second_start", None)
        second_end = getattr(schedule, "second_end", None)
        if kind == "split" and second_start and second_end:
            shift_min = shift_length_minutes(schedule.start_time, schedule.end_time) + shift_length_minutes(
                second_start, second_end
            )
    half_cut = timedelta(minutes=max(shift_min // 2, 1))

    local_out = as_local(now, employee=employee, organization=organization).time()
    end_time = schedule.second_end if kind == "split" and getattr(schedule, "second_end", None) else schedule.end_time
    after_end = minutes_after(local_out, end_time)
    ot_grace = _grace(schedule, "overtime_grace_minutes", OVERTIME_GRACE_MIN)
    early_grace = _grace(schedule, "early_leave_grace_minutes", EARLY_LEAVE_GRACE_MIN)

    if kind == "flexible" and required:
        extra = int(worked.total_seconds() // 60) - shift_min
        record.overtime_minutes = max(0, extra - ot_grace)
        record.early_leave = extra < -early_grace
    else:
        record.overtime_minutes = max(0, after_end - ot_grace)
        record.early_leave = after_end < -early_grace

    record.missing_checkout = False

    if record.status == AttendanceRecord.STATUS_ON_LEAVE:
        return record

    if worked <= half_cut:
        record.status = AttendanceRecord.STATUS_HALF_DAY
        record.early_leave = True
    return record


def refresh_missing_checkout(record: AttendanceRecord, employee=None, now: datetime | None = None) -> AttendanceRecord:
    if record.check_in is None or record.check_out is not None:
        if record.missing_checkout:
            record.missing_checkout = False
        return record
    employee = employee or record.employee
    organization = getattr(employee, "organization", None)
    schedule = schedule_for(employee=employee, organization=organization, on_date=record.date)
    now = now or record.check_in
    local = as_local(now, employee=employee, organization=organization)
    end_time = schedule.second_end if getattr(schedule, "kind", "") == "split" and getattr(schedule, "second_end", None) else schedule.end_time
    after_end = minutes_after(local.time(), end_time)
    ot_grace = _grace(schedule, "overtime_grace_minutes", OVERTIME_GRACE_MIN)
    record.missing_checkout = after_end > ot_grace
    return record
