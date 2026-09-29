import secrets
from datetime import time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from organizations.plans import (
    PLAN_FREE,
    PLAN_LIMITS,
    PLAN_STARTER,
    get_trial_days,
    limits_for,
)


def default_weekend_days():
    return [5, 6]


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


class Organization(models.Model):
    TYPE_COMPANY = "company"
    TYPE_SCHOOL = "school"
    TYPE_CHOICES = [
        (TYPE_COMPANY, "Company"),
        (TYPE_SCHOOL, "School"),
    ]

    STATUS_TRIALING = "trialing"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELED = "canceled"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    org_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_COMPANY)
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    work_start = models.TimeField(default=time(9, 0))
    late_after = models.TimeField(default=time(9, 30))
    weekend_days = models.JSONField(
        default=default_weekend_days,
        blank=True,
        help_text="Python weekdays that are off: 0=Mon … 6=Sun. Default Sat+Sun.",
    )
    is_active = models.BooleanField(default=True)

    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=128, blank=True)
    api_key = models.CharField(max_length=64, unique=True, blank=True)

    notify_late = models.BooleanField(default=True)
    notify_absent = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_whatsapp = models.BooleanField(default=False)
    twilio_account_sid = models.CharField(max_length=80, blank=True)
    twilio_auth_token = models.CharField(max_length=80, blank=True)
    twilio_from_number = models.CharField(max_length=32, blank=True)
    twilio_whatsapp_from = models.CharField(max_length=40, blank=True)

    stripe_customer_id = models.CharField(max_length=80, blank=True)
    stripe_subscription_id = models.CharField(max_length=80, blank=True)
    plan = models.CharField(max_length=20, default=PLAN_STARTER)
    subscription_status = models.CharField(max_length=20, default=STATUS_TRIALING)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    billing_exempt = models.BooleanField(
        default=False,
        help_text="If true, plan is granted by the platform and Stripe is not required.",
    )
    created_via = models.CharField(
        max_length=20,
        default="signup",
        choices=[("signup", "Self signup"), ("platform", "Super admin")],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "org"
            slug = base
            i = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        if not self.api_key:
            self.api_key = generate_api_key()
        created = self.pk is None
        if not self.pk and not self.trial_ends_at and not self.billing_exempt:
            self.trial_ends_at = timezone.now() + timedelta(days=get_trial_days())
        super().save(*args, **kwargs)
        if created:
            self.ensure_default_branch()
            self.ensure_default_shift()
            self.ensure_default_workflows()
            self.ensure_leave_types()

    def ensure_default_branch(self):
        if self.branches.exists():
            return
        Branch.objects.create(
            organization=self,
            name=self.name,
            is_default=True,
            timezone=self.timezone or "Asia/Karachi",
            weekend_days=list(self.weekend_days or default_weekend_days()),
        )

    def default_branch(self):
        return (
            self.branches.filter(is_default=True, is_active=True).first()
            or self.branches.filter(is_active=True).first()
            or self.branches.first()
        )

    def ensure_default_workflows(self):
        try:
            from approvals.bootstrap import seed_workflows

            seed_workflows(self)
        except Exception:
            return

    def ensure_leave_types(self):
        try:
            from attendance.leave_types import seed_leave_types

            seed_leave_types(self)
        except Exception:
            return

    def ensure_default_shift(self):
        if self.shifts.exists():
            return
        Shift.objects.create(
            organization=self,
            name="General",
            start_time=self.work_start or time(9, 0),
            late_after=self.late_after or time(9, 30),
            end_time=time(18, 0),
            is_default=True,
        )

    def default_shift(self, branch=None):
        qs = self.shifts.filter(is_active=True)
        if branch is not None:
            branch_shift = (
                qs.filter(branch=branch, is_default=True).first()
                or qs.filter(branch=branch).first()
            )
            if branch_shift:
                return branch_shift
        return (
            qs.filter(is_default=True, branch__isnull=True).first()
            or qs.filter(is_default=True).first()
            or qs.first()
        )

    def effective_plan(self) -> str:
        if not self.is_active:
            return PLAN_FREE
        if self.billing_exempt:
            return self.plan if self.plan in PLAN_LIMITS else PLAN_STARTER
        if self.subscription_status == self.STATUS_ACTIVE:
            return self.plan if self.plan in PLAN_LIMITS else PLAN_STARTER
        if self.subscription_status == self.STATUS_TRIALING:
            if self.trial_ends_at and timezone.now() < self.trial_ends_at:
                return PLAN_STARTER
            return PLAN_FREE
        if self.subscription_status == self.STATUS_PAST_DUE:
            return self.plan if self.plan in PLAN_LIMITS else PLAN_FREE
        return PLAN_FREE

    def limits(self) -> dict:
        return limits_for(self.effective_plan())

    def has_feature(self, feature: str) -> bool:
        return bool(self.limits().get(feature))

    def rotate_api_key(self) -> str:
        self.api_key = generate_api_key()
        self.save(update_fields=["api_key", "updated_at"])
        return self.api_key


class Membership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_OPERATOR = "operator"
    ROLE_VIEWER = "viewer"
    ROLE_EMPLOYEE = "employee"
    ROLE_PARENT = "parent"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_OPERATOR, "Operator"),
        (ROLE_VIEWER, "Viewer"),
        (ROLE_EMPLOYEE, "Employee / student"),
        (ROLE_PARENT, "Parent / guardian"),
    ]
    STAFF_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)
    PORTAL_ROLES = (ROLE_EMPLOYEE, ROLE_PARENT)

    @classmethod
    def is_staff_role(cls, role: str | None) -> bool:
        return role in cls.STAFF_ROLES

    @classmethod
    def is_portal_role(cls, role: str | None) -> bool:
        return role in cls.PORTAL_ROLES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "membership"
        unique_together = ("user", "organization")
        ordering = ["id"]

    def __str__(self):
        return f"{self.user} @ {self.organization.slug} ({self.role})"


class Invite(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.ROLE_CHOICES)
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_invites",
    )
    token = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invites",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "org_invite"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.email} -> {self.organization.slug}"

    @property
    def is_valid(self) -> bool:
        if self.accepted_at:
            return False
        return timezone.now() < self.expires_at

    @classmethod
    def issue(cls, *, organization, email: str, role: str, invited_by=None, days: int = 7, employee=None):
        return cls.objects.create(
            organization=organization,
            email=email.lower().strip(),
            role=role,
            employee=employee,
            token=secrets.token_urlsafe(32),
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=days),
        )


class PlatformConfig(models.Model):
    trial_days = models.PositiveIntegerField(default=14)
    plan_limits = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_config"

    def __str__(self):
        return "Platform settings"

    @classmethod
    def load(cls) -> "PlatformConfig":
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"trial_days": 14, "plan_limits": {}})
        return obj


class Branch(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofence_radius_m = models.PositiveIntegerField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    weekend_days = models.JSONField(default=default_weekend_days, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "org_branch"
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_branch_name_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.organization.slug} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.timezone:
            self.timezone = self.organization.timezone or "Asia/Karachi"
        if not self.weekend_days:
            self.weekend_days = list(self.organization.weekend_days or default_weekend_days())
        super().save(*args, **kwargs)
        if self.is_default:
            Branch.objects.filter(organization=self.organization, is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )


class Shift(models.Model):
    KIND_FIXED = "fixed"
    KIND_FLEXIBLE = "flexible"
    KIND_NIGHT = "night"
    KIND_SPLIT = "split"
    KIND_CHOICES = [
        (KIND_FIXED, "Fixed"),
        (KIND_FLEXIBLE, "Flexible"),
        (KIND_NIGHT, "Night"),
        (KIND_SPLIT, "Split"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts",
    )
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_FIXED)
    start_time = models.TimeField()
    late_after = models.TimeField()
    end_time = models.TimeField()
    required_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    second_start = models.TimeField(null=True, blank=True)
    second_end = models.TimeField(null=True, blank=True)
    grace_minutes = models.PositiveIntegerField(default=0)
    early_leave_grace_minutes = models.PositiveIntegerField(default=15)
    overtime_grace_minutes = models.PositiveIntegerField(default=15)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "org_shift"
        ordering = ["-is_default", "start_time", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_shift_name_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.organization.slug} / {self.name}"

    def effective_end(self):
        if self.kind == self.KIND_SPLIT and self.second_end:
            return self.second_end
        return self.end_time

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.is_default:
            return
        siblings = Shift.objects.filter(organization=self.organization, is_default=True).exclude(pk=self.pk)
        if self.branch_id:
            siblings.filter(branch_id=self.branch_id).update(is_default=False)
        else:
            siblings.filter(branch__isnull=True).update(is_default=False)
            org = self.organization
            if org.work_start != self.start_time or org.late_after != self.late_after:
                org.work_start = self.start_time
                org.late_after = self.late_after
                org.save(update_fields=["work_start", "late_after", "updated_at"])


class ShiftAssignment(models.Model):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="shift_assignments",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    weekdays = models.JSONField(
        default=list,
        blank=True,
        help_text="Python weekdays 0=Mon … 6=Sun. Empty means every day.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shift_assignment"
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.employee_id} → {self.shift_id} from {self.start_date}"

    def covers(self, day) -> bool:
        if day < self.start_date:
            return False
        if self.end_date and day > self.end_date:
            return False
        days = self.weekdays or []
        if days and day.weekday() not in {int(n) for n in days}:
            return False
        return True
