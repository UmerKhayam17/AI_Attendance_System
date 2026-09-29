from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from rest_framework.exceptions import ValidationError

from attendance.models import LeaveRequest, LeaveType
from attendance.services.workday import daterange, is_non_working
from payroll.models import EmployeeCompensation, PayrollPolicy


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def leave_year_bounds(policy: PayrollPolicy, day: date) -> tuple[date, date]:
    month = max(1, min(12, int(policy.leave_year_start_month or 1)))
    year = day.year if day.month >= month else day.year - 1
    start = date(year, month, 1)
    if month == 1:
        end = date(year, 12, 31)
    else:
        next_start = date(year + 1, month, 1)
        end = next_start - timedelta(days=1)
    return start, end


def workdays_in_range(organization, start: date, end: date) -> int:
    if end < start:
        return 0
    count = 0
    for day in daterange(start, end):
        off, _ = is_non_working(organization, day)
        if not off:
            count += 1
    return count


def used_leave_days(
    employee,
    leave_type: str,
    year_start: date,
    year_end: date,
    exclude_id: int | None = None,
) -> int:
    qs = LeaveRequest.objects.filter(
        employee=employee,
        leave_type=leave_type,
        status=LeaveRequest.STATUS_APPROVED,
        start_date__lte=year_end,
        end_date__gte=year_start,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    org = employee.organization
    total = 0
    for leave in qs:
        start = max(leave.start_date, year_start)
        end = min(leave.end_date, year_end)
        total += workdays_in_range(org, start, end)
    return total


def _hire_date(employee) -> date | None:
    try:
        comp = employee.compensation
    except EmployeeCompensation.DoesNotExist:
        comp = None
    if comp and comp.hire_date:
        return comp.hire_date
    if employee.created_at:
        return employee.created_at.date()
    return None


def in_probation(policy: PayrollPolicy, employee, day: date) -> bool:
    if not policy.probation_months:
        return False
    hired = _hire_date(employee)
    if not hired:
        return False
    ends = add_months(hired, int(policy.probation_months))
    return day < ends


def leave_type_row(organization, leave_type: str) -> LeaveType | None:
    if organization is None:
        return None
    from attendance.leave_types import seed_leave_types

    seed_leave_types(organization)
    return LeaveType.objects.filter(organization=organization, code=leave_type).first()


def entitled_days(policy: PayrollPolicy, leave_type: str, employee, day: date) -> int:
    if leave_type == LeaveRequest.TYPE_UNPAID:
        return 10_000 if policy.unpaid_leave_allowed else 0
    row = leave_type_row(employee.organization, leave_type)
    if row is not None:
        entitled = int(row.entitlement_days or 0)
    elif leave_type == LeaveRequest.TYPE_ANNUAL:
        entitled = int(policy.annual_leave_days)
    elif leave_type == LeaveRequest.TYPE_SICK:
        entitled = int(policy.sick_leave_days)
    elif leave_type == LeaveRequest.TYPE_OTHER:
        entitled = int(policy.other_leave_days)
    else:
        entitled = 0
    if leave_type == LeaveRequest.TYPE_ANNUAL:
        if policy.probation_blocks_annual and in_probation(policy, employee, day):
            return 0
        if policy.carry_forward_annual and int(policy.carry_forward_max_days or 0) > 0:
            year_start, _year_end = leave_year_bounds(policy, day)
            prev_end = year_start - timedelta(days=1)
            prev_start, _ = leave_year_bounds(policy, prev_end)
            unused = max(
                int(row.entitlement_days if row is not None else policy.annual_leave_days)
                - used_leave_days(employee, LeaveRequest.TYPE_ANNUAL, prev_start, prev_end),
                0,
            )
            entitled += min(unused, int(policy.carry_forward_max_days or 0))
    return entitled


def leave_is_paid(policy: PayrollPolicy, leave_type: str, organization=None) -> bool:
    org = organization or getattr(policy, "organization", None)
    row = leave_type_row(org, leave_type) if org else None
    if row is not None:
        return bool(row.paid)
    if leave_type == LeaveRequest.TYPE_ANNUAL:
        return bool(policy.annual_leave_paid)
    if leave_type == LeaveRequest.TYPE_SICK:
        return bool(policy.sick_leave_paid)
    if leave_type == LeaveRequest.TYPE_OTHER:
        return bool(policy.other_leave_paid)
    return False


def request_workdays(leave: LeaveRequest) -> int:
    return workdays_in_range(leave.employee.organization, leave.start_date, leave.end_date)


def assert_leave_allowed(leave: LeaveRequest):
    org = leave.employee.organization
    policy = PayrollPolicy.for_org(org)
    if leave.leave_type == LeaveRequest.TYPE_UNPAID and not policy.unpaid_leave_allowed:
        raise ValidationError({"error": "Unpaid leave is not allowed by company policy"})
    if not policy.enforce_leave_balance:
        return
    if leave.leave_type == LeaveRequest.TYPE_UNPAID:
        return
    year_start, year_end = leave_year_bounds(policy, leave.start_date)
    used = used_leave_days(
        leave.employee,
        leave.leave_type,
        year_start,
        year_end,
        exclude_id=leave.pk,
    )
    requested = request_workdays(leave)
    entitled = entitled_days(policy, leave.leave_type, leave.employee, leave.start_date)
    if entitled <= 0 and requested > 0:
        raise ValidationError({"error": "No paid leave remaining for this type (check probation or allowance)"})
    if used + requested > entitled:
        remaining = max(entitled - used, 0)
        raise ValidationError({
            "error": (
                f"Leave exceeds allowance: {requested} working day(s) requested, "
                f"{remaining} remaining of {entitled} for this leave year"
            )
        })


def balances_for(employee, day: date | None = None) -> dict:
    org = employee.organization
    policy = PayrollPolicy.for_org(org)
    day = day or date.today()
    year_start, year_end = leave_year_bounds(policy, day)
    rows = {}
    type_rows = list(LeaveType.objects.filter(organization=org, is_active=True).order_by("sort_order", "id"))
    pairs = [(row.code, row.name) for row in type_rows] if type_rows else list(LeaveRequest.TYPE_CHOICES)
    for leave_type, label in pairs:
        used = used_leave_days(employee, leave_type, year_start, year_end)
        entitled = entitled_days(policy, leave_type, employee, day)
        paid = leave_is_paid(policy, leave_type, org)
        rows[leave_type] = {
            "type": leave_type,
            "label": label,
            "entitled": entitled if leave_type != LeaveRequest.TYPE_UNPAID else None,
            "used": used,
            "remaining": None if leave_type == LeaveRequest.TYPE_UNPAID else max(entitled - used, 0),
            "paid": paid,
        }
    return {
        "employee_id": employee.employee_id,
        "employee_pk": employee.id,
        "name": employee.display_name,
        "year_start": str(year_start),
        "year_end": str(year_end),
        "in_probation": in_probation(policy, employee, day),
        "balances": rows,
    }


def previous_calendar_month(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    first = today.replace(day=1)
    end = first - timedelta(days=1)
    start = end.replace(day=1)
    return start, end


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)
