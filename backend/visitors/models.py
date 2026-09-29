import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Visitor(models.Model):
    ID_CNIC = "cnic"
    ID_PASSPORT = "passport"
    ID_LICENSE = "license"
    ID_OTHER = "other"
    ID_CHOICES = [
        (ID_CNIC, "CNIC / National ID"),
        (ID_PASSPORT, "Passport"),
        (ID_LICENSE, "Driving license"),
        (ID_OTHER, "Other"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="visitors",
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=120, blank=True)
    id_type = models.CharField(max_length=20, choices=ID_CHOICES, default=ID_CNIC)
    id_number = models.CharField(max_length=80, blank=True)
    photo = models.ImageField(upload_to="visitors/photos/%Y/%m/", blank=True, null=True)
    notes = models.TextField(blank=True)
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "visitor"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "phone"],
                condition=~Q(phone=""),
                name="uniq_visitor_phone_per_org",
            ),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def _public_token() -> str:
    return secrets.token_urlsafe(18)


class Visit(models.Model):
    PURPOSE_MEETING = "meeting"
    PURPOSE_INTERVIEW = "interview"
    PURPOSE_DELIVERY = "delivery"
    PURPOSE_CONTRACTOR = "contractor"
    PURPOSE_PARENT = "parent"
    PURPOSE_VENDOR = "vendor"
    PURPOSE_OTHER = "other"
    PURPOSE_CHOICES = [
        (PURPOSE_MEETING, "Meeting"),
        (PURPOSE_INTERVIEW, "Interview"),
        (PURPOSE_DELIVERY, "Delivery"),
        (PURPOSE_CONTRACTOR, "Contractor"),
        (PURPOSE_PARENT, "Parent / guardian"),
        (PURPOSE_VENDOR, "Vendor"),
        (PURPOSE_OTHER, "Other"),
    ]

    SOURCE_WALKIN = "walkin"
    SOURCE_PREREGISTER = "preregister"
    SOURCE_CHOICES = [
        (SOURCE_WALKIN, "Walk-in"),
        (SOURCE_PREREGISTER, "Pre-registered"),
    ]

    STATUS_EXPECTED = "expected"
    STATUS_CHECKED_IN = "checked_in"
    STATUS_CHECKED_OUT = "checked_out"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_DENIED = "denied"
    STATUS_CHOICES = [
        (STATUS_EXPECTED, "Expected"),
        (STATUS_CHECKED_IN, "On site"),
        (STATUS_CHECKED_OUT, "Checked out"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No show"),
        (STATUS_DENIED, "Denied"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="visits",
    )
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="visits")
    host = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosted_visits",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits",
    )
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default=PURPOSE_MEETING)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_EXPECTED)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_WALKIN)
    expected_at = models.DateTimeField(null=True, blank=True)
    expected_end = models.DateTimeField(null=True, blank=True)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    badge_code = models.CharField(max_length=20, blank=True)
    vehicle_plate = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    public_token = models.CharField(max_length=40, unique=True, default=_public_token, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits_created",
    )
    denied_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "visit"
        ordering = ["-expected_at", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "expected_at"]),
        ]

    def __str__(self):
        return f"{self.visitor} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = _public_token()
        if not self.branch_id and self.organization_id:
            org = self.organization
            org.ensure_default_branch()
            self.branch = org.default_branch()
        super().save(*args, **kwargs)
