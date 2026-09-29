from decimal import Decimal

from django.conf import settings
from django.db import models


class PayrollPolicy(models.Model):
    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_BIWEEKLY = "biweekly"
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_CHOICES = [
        (FREQUENCY_MONTHLY, "Monthly"),
        (FREQUENCY_BIWEEKLY, "Biweekly"),
        (FREQUENCY_WEEKLY, "Weekly"),
    ]

    LATE_NONE = "none"
    LATE_FIXED = "fixed"
    LATE_QUARTER_DAY = "quarter_day"
    LATE_CHOICES = [
        (LATE_NONE, "No late deduction"),
        (LATE_FIXED, "Fixed amount per extra late"),
        (LATE_QUARTER_DAY, "Quarter day per extra late"),
    ]

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="payroll_policy",
    )
    currency = models.CharField(max_length=8, default="PKR")
    pay_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default=FREQUENCY_MONTHLY)
    working_days_per_month = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("26.00"))
    hours_per_day = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("8.00"))

    annual_leave_days = models.PositiveIntegerField(default=14)
    sick_leave_days = models.PositiveIntegerField(default=8)
    other_leave_days = models.PositiveIntegerField(default=0)
    annual_leave_paid = models.BooleanField(default=True)
    sick_leave_paid = models.BooleanField(default=True)
    other_leave_paid = models.BooleanField(default=False)
    unpaid_leave_allowed = models.BooleanField(default=True)
    leave_year_start_month = models.PositiveSmallIntegerField(default=1)
    carry_forward_annual = models.BooleanField(default=False)
    carry_forward_max_days = models.PositiveIntegerField(default=0)
    probation_months = models.PositiveSmallIntegerField(default=0)
    probation_blocks_annual = models.BooleanField(default=True)
    enforce_leave_balance = models.BooleanField(default=True)

    holiday_paid = models.BooleanField(default=True)
    weekend_paid = models.BooleanField(default=True)
    absent_deduct = models.BooleanField(default=True)
    half_day_pay_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.50"))
    late_count_free = models.PositiveSmallIntegerField(default=2)
    late_penalty_mode = models.CharField(max_length=20, choices=LATE_CHOICES, default=LATE_FIXED)
    late_penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    early_leave_deduct = models.BooleanField(default=True)
    early_leave_as_half_day = models.BooleanField(default=True)

    overtime_paid = models.BooleanField(default=True)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"))
    overtime_min_minutes = models.PositiveIntegerField(default=30)
    overtime_requires_approval = models.BooleanField(default=False)

    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    provident_fund_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_policy"

    def __str__(self):
        return f"Payroll policy {self.organization_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_leave_types()

    def sync_leave_types(self):
        try:
            from attendance.models import LeaveType
        except Exception:
            return
        mapping = {
            "annual": (self.annual_leave_days, self.annual_leave_paid),
            "sick": (self.sick_leave_days, self.sick_leave_paid),
            "other": (self.other_leave_days, self.other_leave_paid),
        }
        for code, (days, paid) in mapping.items():
            LeaveType.objects.filter(organization_id=self.organization_id, code=code).update(
                entitlement_days=int(days or 0),
                paid=bool(paid),
            )

    @classmethod
    def for_org(cls, organization) -> "PayrollPolicy":
        obj, created = cls.objects.get_or_create(organization=organization)
        if created:
            obj.sync_leave_types()
        return obj


class EmployeeCompensation(models.Model):
    PAY_MONTHLY = "monthly"
    PAY_DAILY = "daily"
    PAY_HOURLY = "hourly"
    PAY_CHOICES = [
        (PAY_MONTHLY, "Monthly salary"),
        (PAY_DAILY, "Daily wage"),
        (PAY_HOURLY, "Hourly"),
    ]

    employee = models.OneToOneField(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="compensation",
    )
    pay_type = models.CharField(max_length=20, choices=PAY_CHOICES, default=PAY_MONTHLY)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    medical_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    hire_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    account_title = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employee_compensation"

    def __str__(self):
        return f"Pay {self.employee.employee_id}"

    @property
    def total_allowances(self) -> Decimal:
        return (
            self.housing_allowance
            + self.transport_allowance
            + self.medical_allowance
            + self.other_allowance
        )

    @property
    def monthly_gross(self) -> Decimal:
        return self.basic_salary + self.total_allowances


class PayrollRun(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_FINALIZED = "finalized"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_FINALIZED, "Finalized"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="payroll_runs",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_runs_created",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_runs_finalized",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_run"
        ordering = ["-period_start", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "period_start", "period_end"],
                name="uniq_payroll_period_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.organization_id} {self.period_start}–{self.period_end} ({self.status})"


class Payslip(models.Model):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="payslips",
    )
    pay_type = models.CharField(max_length=20)
    working_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    late_days = models.PositiveIntegerField(default=0)
    half_days = models.PositiveIntegerField(default=0)
    absent_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    paid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    unpaid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    overtime_minutes = models.PositiveIntegerField(default=0)
    early_leave_days = models.PositiveIntegerField(default=0)

    basic_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    absent_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    late_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unpaid_leave_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    half_day_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    early_leave_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    provident_fund = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payslip"
        ordering = ["employee__employee_id"]
        constraints = [
            models.UniqueConstraint(fields=["run", "employee"], name="uniq_payslip_per_run_employee"),
        ]

    def __str__(self):
        return f"Payslip {self.employee.employee_id} run {self.run_id}"
