from django.db import models
from employees.models import Employee


class AttendanceRecord(models.Model):
    STATUS_PRESENT = "present"
    STATUS_LATE = "late"
    STATUS_ABSENT = "absent"
    STATUS_HALF_DAY = "half_day"
    STATUS_ON_LEAVE = "on_leave"

    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_LATE, "Late"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_HALF_DAY, "Half Day"),
        (STATUS_ON_LEAVE, "On Leave"),
    ]

    SOURCE_CCTV = "cctv"
    SOURCE_MANUAL = "manual"
    SOURCE_WEBCAM = "webcam"
    SOURCE_MOBILE = "mobile"

    SOURCE_CHOICES = [
        (SOURCE_CCTV, "CCTV"),
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_WEBCAM, "Webcam"),
        (SOURCE_MOBILE, "Mobile camera"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PRESENT,
    )
    check_in_confidence = models.FloatField(null=True, blank=True)
    check_out_confidence = models.FloatField(null=True, blank=True)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_CCTV,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True)
    overtime_minutes = models.PositiveIntegerField(default=0)
    early_leave = models.BooleanField(default=False)
    missing_checkout = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance_record"
        unique_together = ("employee", "date")
        ordering = ["-date", "employee__employee_id"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} ({self.status})"


class Holiday(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="holidays",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="holidays",
    )
    date = models.DateField()
    name = models.CharField(max_length=120)
    repeats_yearly = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "org_holiday"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "date"],
                condition=models.Q(branch__isnull=True),
                name="uniq_org_holiday_date",
            ),
            models.UniqueConstraint(
                fields=["organization", "branch", "date"],
                condition=models.Q(branch__isnull=False),
                name="uniq_branch_holiday_date",
            ),
        ]

    def __str__(self):
        return f"{self.organization_id} {self.date} {self.name}"


class LeaveRequest(models.Model):
    TYPE_ANNUAL = "annual"
    TYPE_SICK = "sick"
    TYPE_CASUAL = "casual"
    TYPE_MATERNITY = "maternity"
    TYPE_EMERGENCY = "emergency"
    TYPE_UNPAID = "unpaid"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_ANNUAL, "Annual"),
        (TYPE_SICK, "Sick"),
        (TYPE_CASUAL, "Casual"),
        (TYPE_MATERNITY, "Maternity"),
        (TYPE_EMERGENCY, "Emergency"),
        (TYPE_UNPAID, "Unpaid"),
        (TYPE_OTHER, "Other"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_ANNUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_request"
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.start_date}–{self.end_date} ({self.status})"


class NotificationLog(models.Model):
    KIND_LATE = "late"
    KIND_ABSENT = "absent"
    KIND_LEAVE = "leave"
    KIND_CORRECTION = "correction"
    KIND_APPROVAL = "approval"
    KIND_CHOICES = [
        (KIND_LATE, "Late"),
        (KIND_ABSENT, "Absent"),
        (KIND_LEAVE, "Leave"),
        (KIND_CORRECTION, "Correction"),
        (KIND_APPROVAL, "Approval"),
    ]

    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_WEBHOOK = "webhook"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
        (CHANNEL_WEBHOOK, "Webhook"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    date = models.DateField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    recipient = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_log"
        ordering = ["-sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date", "kind", "channel"],
                name="uniq_notification_per_day_channel",
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} {self.kind} {self.date} {self.channel}"


class LeaveType(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="leave_types",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=80)
    paid = models.BooleanField(default=True)
    entitlement_days = models.PositiveIntegerField(default=0)
    requires_document = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "leave_type"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_leave_type_code_per_org"),
        ]

    def __str__(self):
        return f"{self.organization_id} {self.code}"


class AttendanceCorrection(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance_corrections",
    )
    date = models.DateField()
    requested_check_in = models.DateTimeField(null=True, blank=True)
    requested_check_out = models.DateTimeField(null=True, blank=True)
    original_check_in = models.DateTimeField(null=True, blank=True)
    original_check_out = models.DateTimeField(null=True, blank=True)
    original_status = models.CharField(max_length=20, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    decided_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_corrections_decided",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance_correction"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.date} ({self.status})"

    def original_snapshot(self):
        return {
            "check_in": self.original_check_in.isoformat() if self.original_check_in else None,
            "check_out": self.original_check_out.isoformat() if self.original_check_out else None,
            "status": self.original_status,
        }


class OvertimeRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]
    SOURCE_MANUAL = "manual"
    SOURCE_AUTO = "auto"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_AUTO, "Auto"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="overtime_requests",
    )
    date = models.DateField()
    minutes = models.PositiveIntegerField()
    reason = models.TextField(blank=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    decided_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overtime_requests_decided",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "overtime_request"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.date} {self.minutes}m ({self.status})"
