from django.db import models
from employees.models import Employee


class Camera(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="cameras",
    )
    ZONE_MIXED = "mixed"
    ZONE_ENTRY = "entry"
    ZONE_EXIT = "exit"
    ZONE_INTERIOR = "interior"
    ZONE_CHOICES = [
        (ZONE_MIXED, "Mixed (check-in then check-out)"),
        (ZONE_ENTRY, "Entry (check-in only)"),
        (ZONE_EXIT, "Exit (check-out only)"),
        (ZONE_INTERIOR, "Interior (check-in if missing, never check-out)"),
    ]

    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="cameras",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150, blank=True)
    rtsp_url = models.CharField(max_length=500)
    zone = models.CharField(
        max_length=16,
        choices=ZONE_CHOICES,
        default=ZONE_MIXED,
        help_text="Controls whether this camera can check people in, out, or both.",
    )
    HEALTH_ONLINE = "online"
    HEALTH_DEGRADED = "degraded"
    HEALTH_OFFLINE = "offline"
    HEALTH_STOPPED = "stopped"
    HEALTH_CHOICES = [
        (HEALTH_ONLINE, "Online"),
        (HEALTH_DEGRADED, "Degraded"),
        (HEALTH_OFFLINE, "Offline"),
        (HEALTH_STOPPED, "Stopped"),
    ]

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    health_status = models.CharField(
        max_length=16,
        choices=HEALTH_CHOICES,
        default=HEALTH_STOPPED,
    )
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=250, blank=True)
    fps = models.FloatField(null=True, blank=True)
    last_health_alert_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "camera"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.branch_id and self.organization_id:
            org = self.organization
            org.ensure_default_branch()
            self.branch = org.default_branch()
        super().save(*args, **kwargs)


class DetectionSnapshot(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="detection_snapshots",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detection_snapshots",
    )
    camera_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="detections/%Y/%m/%d/")
    confidence = models.FloatField(default=0.0)
    attendance_action = models.CharField(max_length=32, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "detection_snapshot"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.employee.employee_id} @ {self.camera_name} ({self.detected_at})"


class FaceEnrollment(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="face_enrollment"
    )

    profile_image = models.ImageField(
        upload_to="employees/profile/",
        blank=True,
        null=True
    )

    dataset_folder = models.CharField(
        max_length=255,
        unique=True
    )

    total_images = models.PositiveIntegerField(default=0)
    is_enrolled = models.BooleanField(default=False)
    is_trained = models.BooleanField(default=False)
    model_version = models.CharField(
        max_length=50,
        default="InsightFace_v1"
    )
    embedding = models.JSONField(null=True, blank=True)
    embeddings = models.JSONField(
        null=True,
        blank=True,
        help_text="Per-pose ArcFace vectors used for nearest-neighbor matching.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "face_enrollment"
        verbose_name = "Face Enrollment"
        verbose_name_plural = "Face Enrollments"

    def __str__(self):
        return f"{self.employee.employee_id} - {self.employee.first_name}"


class MatchReview(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    REASON_LOW = "low_confidence"
    REASON_AMBIGUOUS = "ambiguous"
    REASON_CHOICES = [
        (REASON_LOW, "Low confidence"),
        (REASON_AMBIGUOUS, "Ambiguous identity"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="match_reviews",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_reviews",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_reviews",
    )
    camera_name = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to="reviews/%Y/%m/%d/", blank=True, null=True)
    confidence = models.FloatField(default=0.0)
    second_best = models.FloatField(null=True, blank=True)
    reason = models.CharField(max_length=32, choices=REASON_CHOICES, default=REASON_LOW)
    suggested_employee_id = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    track_id = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, default="cctv")
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    attendance_action = models.CharField(max_length=32, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "match_review"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"review {self.suggested_employee_id} {self.status} ({self.confidence:.2f})"


class RecognitionEvent(models.Model):
    KIND_RECOGNIZED = "recognized"
    KIND_UNKNOWN = "unknown"
    KIND_SPOOF = "spoof"
    KIND_REVIEW = "review"
    KIND_ANOMALY = "anomaly"
    KIND_CAMERA = "camera"
    KIND_CHOICES = [
        (KIND_RECOGNIZED, "Recognized"),
        (KIND_UNKNOWN, "Unknown person"),
        (KIND_SPOOF, "Spoof attempt"),
        (KIND_REVIEW, "Queued for review"),
        (KIND_ANOMALY, "Anomaly"),
        (KIND_CAMERA, "Camera health"),
    ]

    STATUS_OPEN = "open"
    STATUS_DISMISSED = "dismissed"
    STATUS_ASSIGNED = "assigned"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_DISMISSED, "Dismissed"),
        (STATUS_ASSIGNED, "Assigned"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="recognition_events",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recognition_events",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recognition_events",
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    camera_name = models.CharField(max_length=100, blank=True)
    confidence = models.FloatField(default=0.0)
    message = models.CharField(max_length=250, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to="events/%Y/%m/%d/", blank=True, null=True)
    track_id = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, default="cctv")
    attendance_action = models.CharField(max_length=32, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recognition_event"
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["organization", "detected_at"]),
            models.Index(fields=["organization", "kind", "status"]),
        ]

    def __str__(self):
        return f"{self.kind} {self.camera_name} ({self.detected_at})"


class CameraDwellSession(models.Model):
    """Time a recognized employee stays in a camera's view (ByteTrack session)."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="dwell_sessions",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name="dwell_sessions",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="dwell_sessions",
    )
    track_id = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    seconds = models.PositiveIntegerField(default=0)
    peak_confidence = models.FloatField(default=0.0)

    class Meta:
        db_table = "camera_dwell_session"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["organization", "ended_at"]),
            models.Index(fields=["camera", "ended_at"]),
            models.Index(fields=["employee", "started_at"]),
        ]

    def __str__(self):
        return f"{self.employee_id} cam {self.camera_id} {self.seconds}s"
