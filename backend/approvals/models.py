from django.conf import settings
from django.db import models


class ApprovalWorkflow(models.Model):
    KIND_LEAVE = "leave"
    KIND_OVERTIME = "overtime"
    KIND_CORRECTION = "attendance_correction"
    KIND_EXIT = "exit"
    KIND_CHOICES = [
        (KIND_LEAVE, "Leave"),
        (KIND_OVERTIME, "Overtime"),
        (KIND_CORRECTION, "Attendance correction"),
        (KIND_EXIT, "Exit / resignation"),
    ]
    KINDS = (KIND_LEAVE, KIND_OVERTIME, KIND_CORRECTION, KIND_EXIT)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="approval_workflows",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "approval_workflow"
        unique_together = ("organization", "kind")
        ordering = ["kind"]

    def __str__(self):
        return f"{self.organization_id} {self.kind}"


class ApprovalStep(models.Model):
    ROLE_MANAGER = "manager"
    ROLE_ADMIN = "admin"
    ROLE_OWNER = "owner"
    ROLE_CHOICES = [
        (ROLE_MANAGER, "Manager"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_OWNER, "Owner"),
    ]

    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveSmallIntegerField(default=1)
    assignee_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)

    class Meta:
        db_table = "approval_step"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.workflow.kind} #{self.order} {self.assignee_role}"


class ApprovalRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    kind = models.CharField(max_length=32, choices=ApprovalWorkflow.KIND_CHOICES)
    target_id = models.PositiveIntegerField()
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_submitted",
    )
    current_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="open_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "approval_request"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "kind", "target_id"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.kind} #{self.target_id} ({self.status})"


class ApprovalAction(models.Model):
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_CHOICES = [
        (ACTION_APPROVE, "Approve"),
        (ACTION_REJECT, "Reject"),
    ]

    request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_actions",
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval_action"
        ordering = ["created_at"]


class AuditEvent(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64, blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=240, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_event"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "created_at"])]

    def __str__(self):
        return f"{self.action} {self.model} {self.object_id}"


class InAppNotification(models.Model):
    KIND_APPROVAL = "approval"
    KIND_LEAVE = "leave"
    KIND_CORRECTION = "correction"
    KIND_OVERTIME = "overtime"
    KIND_EXIT = "exit"
    KIND_PAYROLL = "payroll"
    KIND_CAMERA = "camera"
    KIND_SECURITY = "security"
    KIND_VISITOR = "visitor"
    KIND_CHOICES = [
        (KIND_APPROVAL, "Approval"),
        (KIND_LEAVE, "Leave"),
        (KIND_CORRECTION, "Correction"),
        (KIND_OVERTIME, "Overtime"),
        (KIND_EXIT, "Exit"),
        (KIND_PAYROLL, "Payroll"),
        (KIND_CAMERA, "Camera"),
        (KIND_SECURITY, "Security"),
        (KIND_VISITOR, "Visitor"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_APPROVAL)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "in_app_notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]
