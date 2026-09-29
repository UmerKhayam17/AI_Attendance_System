from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from attendance.models import AttendanceRecord, LeaveRequest
from attendance.services.workday import daterange, is_non_working, leave_on
from employees.models import Employee
from payroll.models import EmployeeCompensation, PayrollPolicy, PayrollRun, Payslip
from payroll.services.leave_policy import leave_is_paid, workdays_in_range


TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def daily_rate(policy: PayrollPolicy, compensation: EmployeeCompensation) -> Decimal:
    hours = policy.hours_per_day or Decimal("8")
    divisor = policy.working_days_per_month or Decimal("26")
    if compensation.pay_type == EmployeeCompensation.PAY_HOURLY:
        return money(compensation.basic_salary * hours)
    if compensation.pay_type == EmployeeCompensation.PAY_DAILY:
        return money(compensation.basic_salary)
    return money((compensation.basic_salary + compensation.total_allowances) / divisor)


def hourly_rate(policy: PayrollPolicy, compensation: EmployeeCompensation) -> Decimal:
    hours = policy.hours_per_day or Decimal("8")
    if compensation.pay_type == EmployeeCompensation.PAY_HOURLY:
        return money(compensation.basic_salary)
    return money(daily_rate(policy, compensation) / hours)


def _period_allowances(policy: PayrollPolicy, compensation: EmployeeCompensation, workdays: int) -> Decimal:
    total = compensation.total_allowances
    if compensation.pay_type == EmployeeCompensation.PAY_MONTHLY:
        return money(total)
    divisor = policy.working_days_per_month or Decimal("26")
    return money(total * Decimal(workdays) / divisor)


def _period_basic(policy: PayrollPolicy, compensation: EmployeeCompensation, paid_units: Decimal, workdays: int) -> Decimal:
    if compensation.pay_type == EmployeeCompensation.PAY_MONTHLY:
        divisor = policy.working_days_per_month or Decimal("26")
        return money(compensation.basic_salary * Decimal(workdays) / divisor) if workdays else money(compensation.basic_salary)
    if compensation.pay_type == EmployeeCompensation.PAY_HOURLY:
        hours = policy.hours_per_day or Decimal("8")
        return money(compensation.basic_salary * hours * paid_units)
    return money(compensation.basic_salary * paid_units)


@transaction.atomic
def generate_payroll_run(organization, period_start: date, period_end: date, user=None) -> PayrollRun:
    if period_end < period_start:
        raise ValueError("period_end must be on or after period_start")

    existing = PayrollRun.objects.filter(
        organization=organization,
        period_start=period_start,
        period_end=period_end,
    ).first()
    if existing and existing.status == PayrollRun.STATUS_FINALIZED:
        raise ValueError("This period is already finalized")
    if existing:
        existing.payslips.all().delete()
        run = existing
        run.notes = ""
        run.warnings = []
        run.created_by = user or run.created_by
        run.save(update_fields=["notes", "warnings", "created_by", "updated_at"])
    else:
        run = PayrollRun.objects.create(
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            created_by=user,
        )

    policy = PayrollPolicy.for_org(organization)
    employees = list(
        Employee.objects.filter(organization=organization, is_active=True)
        .select_related("compensation", "department")
        .order_by("employee_id")
    )
    records = AttendanceRecord.objects.filter(
        employee__organization=organization,
        date__gte=period_start,
        date__lte=period_end,
    )
    by_emp_date: dict[int, dict[date, AttendanceRecord]] = defaultdict(dict)
    for rec in records:
        by_emp_date[rec.employee_id][rec.date] = rec

    warnings = []
    workdays = workdays_in_range(organization, period_start, period_end)

    for employee in employees:
        try:
            compensation = employee.compensation
        except EmployeeCompensation.DoesNotExist:
            warnings.append(f"{employee.employee_id} {employee.display_name}: no salary set")
            continue
        if compensation.basic_salary <= 0:
            warnings.append(f"{employee.employee_id} {employee.display_name}: basic salary is zero")
            continue
        _build_payslip(
            run,
            policy,
            employee,
            compensation,
            by_emp_date.get(employee.id, {}),
            workdays,
        )

    run.warnings = warnings
    run.save(update_fields=["warnings", "updated_at"])
    return run


def _build_payslip(
    run: PayrollRun,
    policy: PayrollPolicy,
    employee: Employee,
    compensation: EmployeeCompensation,
    records: dict[date, AttendanceRecord],
    workdays: int,
):
    present = late = half = absent = paid_leave = unpaid_leave = early = extra_paid_off = 0
    overtime_minutes = 0
    org = employee.organization

    for day in daterange(run.period_start, run.period_end):
        off, reason = is_non_working(org, day)
        if off:
            if compensation.pay_type != EmployeeCompensation.PAY_MONTHLY:
                weekend = reason == "Weekend"
                if weekend and policy.weekend_paid:
                    extra_paid_off += 1
                elif not weekend and policy.holiday_paid:
                    extra_paid_off += 1
            continue
        leave = leave_on(employee, day)
        if leave:
            if leave_is_paid(policy, leave.leave_type, org):
                paid_leave += 1
            else:
                unpaid_leave += 1
            continue
        rec = records.get(day)
        if rec is None:
            if policy.absent_deduct:
                absent += 1
            continue
        if rec.status == AttendanceRecord.STATUS_ON_LEAVE:
            continue
        if rec.status == AttendanceRecord.STATUS_HALF_DAY:
            half += 1
        elif rec.status == AttendanceRecord.STATUS_ABSENT:
            absent += 1
        else:
            present += 1
            if rec.status == AttendanceRecord.STATUS_LATE:
                late += 1
            if rec.early_leave and rec.status != AttendanceRecord.STATUS_HALF_DAY:
                early += 1
        overtime_minutes += rec.overtime_minutes or 0

    if policy.overtime_requires_approval:
        from attendance.models import OvertimeRequest

        approved = {
            row.date: row.minutes
            for row in OvertimeRequest.objects.filter(
                employee=employee,
                date__gte=run.period_start,
                date__lte=run.period_end,
                status=OvertimeRequest.STATUS_APPROVED,
            )
        }
        overtime_minutes = sum(approved.values())

    rate = daily_rate(policy, compensation)
    extra_lates = max(late - int(policy.late_count_free or 0), 0)
    late_deduction = ZERO
    if extra_lates and policy.late_penalty_mode == PayrollPolicy.LATE_FIXED:
        late_deduction = money(Decimal(extra_lates) * policy.late_penalty_amount)
    elif extra_lates and policy.late_penalty_mode == PayrollPolicy.LATE_QUARTER_DAY:
        late_deduction = money(Decimal(extra_lates) * rate * Decimal("0.25"))

    half_deduction = ZERO
    if half:
        half_deduction = money(Decimal(half) * rate * (Decimal("1") - (policy.half_day_pay_factor or Decimal("0.5"))))

    absent_deduction = money(Decimal(absent) * rate) if policy.absent_deduct else ZERO
    unpaid_deduction = money(Decimal(unpaid_leave) * rate)
    early_deduction = ZERO
    if policy.early_leave_deduct and early:
        factor = policy.half_day_pay_factor if policy.early_leave_as_half_day else Decimal("0.25")
        early_deduction = money(Decimal(early) * rate * (Decimal("1") - factor))

    paid_units = (
        Decimal(present)
        + Decimal(paid_leave)
        + Decimal(extra_paid_off)
        + Decimal(half) * (policy.half_day_pay_factor or Decimal("0.5"))
    )
    if compensation.pay_type == EmployeeCompensation.PAY_MONTHLY:
        if policy.pay_frequency == PayrollPolicy.FREQUENCY_MONTHLY:
            basic = money(compensation.basic_salary)
            allowances = money(compensation.total_allowances)
        else:
            divisor = policy.working_days_per_month or Decimal("26")
            factor = Decimal(workdays) / divisor if divisor else Decimal("1")
            basic = money(compensation.basic_salary * factor)
            allowances = money(compensation.total_allowances * factor)
    else:
        basic = _period_basic(policy, compensation, paid_units, workdays)
        allowances = _period_allowances(policy, compensation, workdays)
        absent_deduction = ZERO
        unpaid_deduction = ZERO
        half_deduction = ZERO

    overtime_pay = ZERO
    billable_ot = overtime_minutes if overtime_minutes >= int(policy.overtime_min_minutes or 0) else 0
    if policy.overtime_paid and billable_ot:
        overtime_pay = money(
            (Decimal(billable_ot) / Decimal("60"))
            * hourly_rate(policy, compensation)
            * (policy.overtime_multiplier or Decimal("1"))
        )

    other_deduction = money(compensation.other_deduction)
    pf = money(compensation.basic_salary * (policy.provident_fund_percent or ZERO) / Decimal("100"))

    attendance_deductions = absent_deduction + late_deduction + unpaid_deduction + half_deduction + early_deduction
    taxable = basic + allowances + overtime_pay - attendance_deductions - other_deduction - pf
    if taxable < ZERO:
        taxable = ZERO
    tax = money(taxable * (policy.tax_percent or ZERO) / Decimal("100"))

    deductions = attendance_deductions + other_deduction + pf + tax
    gross = basic + allowances + overtime_pay
    net = money(gross - deductions)
    if net < ZERO:
        net = ZERO

    Payslip.objects.create(
        run=run,
        employee=employee,
        pay_type=compensation.pay_type,
        working_days=Decimal(workdays),
        present_days=Decimal(present),
        late_days=late,
        half_days=half,
        absent_days=Decimal(absent),
        paid_leave_days=Decimal(paid_leave),
        unpaid_leave_days=Decimal(unpaid_leave),
        overtime_minutes=overtime_minutes,
        early_leave_days=early,
        basic_pay=basic,
        allowances=allowances,
        overtime_pay=overtime_pay,
        absent_deduction=absent_deduction,
        late_deduction=late_deduction,
        unpaid_leave_deduction=unpaid_deduction,
        half_day_deduction=half_deduction,
        early_leave_deduction=early_deduction,
        tax=tax,
        provident_fund=pf,
        other_deduction=other_deduction,
        gross_pay=gross,
        total_deductions=deductions,
        net_pay=net,
        breakdown={
            "currency": policy.currency,
            "daily_rate": str(rate),
            "hourly_rate": str(hourly_rate(policy, compensation)),
            "extra_lates": extra_lates,
            "billable_overtime_minutes": billable_ot,
            "bank_name": compensation.bank_name,
            "account_title": compensation.account_title,
            "account_number": compensation.account_number,
        },
    )


def snapshot_attendance(run: PayrollRun):
    records = AttendanceRecord.objects.filter(
        employee__organization=run.organization,
        date__gte=run.period_start,
        date__lte=run.period_end,
    ).select_related("employee")
    by_emp: dict[int, list] = defaultdict(list)
    for rec in records:
        by_emp[rec.employee_id].append({
            "date": str(rec.date),
            "status": rec.status,
            "check_in": rec.check_in.isoformat() if rec.check_in else None,
            "check_out": rec.check_out.isoformat() if rec.check_out else None,
            "overtime_minutes": rec.overtime_minutes or 0,
        })
    for slip in run.payslips.all():
        breakdown = dict(slip.breakdown or {})
        breakdown["attendance_snapshot"] = by_emp.get(slip.employee_id, [])
        breakdown["locked"] = True
        slip.breakdown = breakdown
        slip.save(update_fields=["breakdown"])
