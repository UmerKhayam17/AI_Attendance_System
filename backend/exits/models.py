from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q


DEFAULT_CHECKLIST = [
    ("it", "Laptop / company device returned"),
    ("it", "Email and software accounts disabled"),
    ("access", "ID card / access badge returned"),
    ("access", "Face enrollment / biometric access revoked"),
    ("finance", "Outstanding advances recovered"),
    ("finance", "Final settlement (F&F) prepared"),
    ("hr", "Exit interview completed"),
    ("hr", "Relieving / experience letter issued"),
    ("assets", "Keys, uniform, and other assets returned"),
]


class ExitPolicy(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="exit_policy",
    )
    notice_period_days = models.PositiveIntegerField(default=30)
    probation_notice_days = models.PositiveIntegerField(default=7)
    require_clearance = models.BooleanField(default=True)
    require_interview = models.BooleanField(default=True)
    auto_deactivate = models.BooleanField(default=True)
    allow_notice_buyout = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exit_policy"

    def __str__(self):
        return f"Exit policy {self.organization_id}"

    @classmethod
    def for_org(cls, organization) -> "ExitPolicy":
        obj, created = cls.objects.get_or_create(organization=organization)
        if created or not organization.exit_checklist_templates.exists():
            seed_checklist_templates(organization)
        return obj


def seed_checklist_templates(organization):
    if organization.exit_checklist_templates.exists():
        return
    ExitChecklistTemplate.objects.bulk_create(
        [
            ExitChecklistTemplate(organization=organization, category=cat, title=title, sort_order=i)
            for i, (cat, title) in enumerate(DEFAULT_CHECKLIST)
        ]
    )


class ExitChecklistTemplate(models.Model):
    CATEGORY_IT = "it"
    CATEGORY_FINANCE = "finance"
    CATEGORY_HR = "hr"
    CATEGORY_ACCESS = "access"
    CATEGORY_ASSETS = "assets"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_IT, "IT"),
        (CATEGORY_FINANCE, "Finance"),
        (CATEGORY_HR, "HR"),
        (CATEGORY_ACCESS, "Access"),
        (CATEGORY_ASSETS, "Assets"),
        (CATEGORY_OTHER, "Other"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="exit_checklist_templates",
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    title = models.CharField(max_length=200)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "exit_checklist_template"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class ExitCase(models.Model):
    TYPE_RESIGNATION = "resignation"
    TYPE_TERMINATION = "termination"
    TYPE_CONTRACT_END = "contract_end"
    TYPE_RETIREMENT = "retirement"
    TYPE_ABSCONDING = "absconding"
    TYPE_CHOICES = [
        (TYPE_RESIGNATION, "Resignation"),
        (TYPE_TERMINATION, "Termination"),
        (TYPE_CONTRACT_END, "End of contract"),
        (TYPE_RETIREMENT, "Retirement"),
        (TYPE_ABSCONDING, "Absconding"),
    ]

    STATUS_INITIATED = "initiated"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="exit_cases",
    )
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="exit_cases",
    )
    exit_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_RESIGNATION)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    resignation_date = models.DateField(default=date.today)
    last_working_day = models.DateField()
    notice_period_days = models.PositiveIntegerField(default=30)
    notice_buyout_days = models.PositiveIntegerField(default=0)
    reason = models.TextField(blank=True)
    handover_notes = models.TextField(blank=True)
    interview_notes = models.TextField(blank=True)
    interview_completed = models.BooleanField(default=False)
    rehire_eligible = models.BooleanField(default=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exit_cases_initiated",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    final_settlement_notes = models.TextField(blank=True)
    last_payroll_run = models.ForeignKey(
        "payroll.PayrollRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exit_cases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exit_case"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(status__in=["initiated", "in_progress"]),
                name="uniq_open_exit_per_employee",
            ),
        ]

    def __str__(self):
        return f"Exit {self.employee.employee_id} ({self.status})"

    @property
    def clearance_done(self) -> bool:
        items = list(self.checklist_items.all())
        return bool(items) and all(item.is_cleared for item in items)

    @property
    def notice_shortfall_days(self) -> int:
        served = (self.last_working_day - self.resignation_date).days
        return max(int(self.notice_period_days) - served - int(self.notice_buyout_days or 0), 0)


class ExitClearanceItem(models.Model):
    case = models.ForeignKey(ExitCase, on_delete=models.CASCADE, related_name="checklist_items")
    category = models.CharField(max_length=20, choices=ExitChecklistTemplate.CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    is_cleared = models.BooleanField(default=False)
    notes = models.CharField(max_length=240, blank=True)
    cleared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exit_clearances",
    )
    cleared_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "exit_clearance_item"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


def notice_days_for(policy: ExitPolicy, employee, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    try:
        from payroll.models import PayrollPolicy
        from payroll.services.leave_policy import in_probation

        if in_probation(PayrollPolicy.for_org(employee.organization), employee, on_date):
            return int(policy.probation_notice_days)
    except Exception:
        pass
    return int(policy.notice_period_days)


def suggested_last_working_day(policy: ExitPolicy, employee, resignation_date: date) -> date:
    return resignation_date + timedelta(days=notice_days_for(policy, employee, resignation_date))
