"""Scan working days for people still missing after late_after."""
from __future__ import annotations

import logging

from organizations.localtime import local_date, local_time

from attendance.models import AttendanceRecord, NotificationLog
from attendance.services.notifier import notify_event
from attendance.services.workday import expected_employees
from employees.models import Employee
from organizations.models import Organization
from organizations.shifts import schedule_for

logger = logging.getLogger(__name__)


def send_absent_alerts(*, organization=None) -> int:
    orgs = Organization.objects.filter(is_active=True)
    if organization is not None:
        orgs = orgs.filter(pk=organization.pk)

    sent = 0
    for org in orgs:
        if not org.notify_absent:
            continue
        people = list(
            Employee.objects.filter(organization=org, is_active=True).select_related(
                "shift", "organization", "branch"
            )
        )
        by_day: dict = {}
        for emp in people:
            day = local_date(employee=emp, organization=org)
            by_day.setdefault(day, []).append(emp)
        for day, day_people in by_day.items():
            expected = expected_employees(org, day, day_people)
            if not expected:
                continue
            present_ids = set(
                AttendanceRecord.objects.filter(
                    date=day,
                    employee__in=expected,
                    check_in__isnull=False,
                ).values_list("employee_id", flat=True)
            )
            for emp in expected:
                if emp.id in present_ids:
                    continue
                now_t = local_time(employee=emp, organization=org)
                schedule = schedule_for(employee=emp, organization=org, on_date=day)
                if now_t < schedule.late_after:
                    continue
                if NotificationLog.objects.filter(
                    employee=emp, date=day, kind=NotificationLog.KIND_ABSENT
                ).exists():
                    continue
                sent += notify_event(emp, NotificationLog.KIND_ABSENT)
    return sent
