from datetime import date

from rest_framework.exceptions import ValidationError

from payroll.models import PayrollRun


def period_is_locked(organization, day: date) -> bool:
    if organization is None or day is None:
        return False
    return PayrollRun.objects.filter(
        organization=organization,
        status=PayrollRun.STATUS_FINALIZED,
        period_start__lte=day,
        period_end__gte=day,
    ).exists()


def assert_dates_unlocked(organization, start: date, end: date | None = None):
    end = end or start
    if end < start:
        start, end = end, start
    locked = PayrollRun.objects.filter(
        organization=organization,
        status=PayrollRun.STATUS_FINALIZED,
        period_start__lte=end,
        period_end__gte=start,
    ).exists()
    if locked:
        raise ValidationError(
            {"error": "This date is in a finalized payroll period and cannot be changed"}
        )
