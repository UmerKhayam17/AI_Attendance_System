from django.contrib import admin

from .models import Camera, CameraDwellSession, DetectionSnapshot, FaceEnrollment, MatchReview, RecognitionEvent


@admin.register(FaceEnrollment)
class FaceEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "is_enrolled",
        "is_trained",
        "total_images",
        "created_at",
    )
    search_fields = (
        "employee__employee_id",
        "employee__first_name",
        "employee__last_name",
    )
    list_filter = ("is_enrolled", "is_trained")


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "branch", "location", "zone", "health_status", "is_active", "sort_order")
    list_filter = ("is_active", "health_status", "zone", "organization", "branch")
    search_fields = ("name", "location", "rtsp_url")
    ordering = ("sort_order", "id")


@admin.register(DetectionSnapshot)
class DetectionSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "camera_name",
        "confidence",
        "attendance_action",
        "detected_at",
    )
    list_filter = ("camera_name", "attendance_action")
    search_fields = ("employee__employee_id", "camera_name")
    readonly_fields = ("detected_at",)


@admin.register(MatchReview)
class MatchReviewAdmin(admin.ModelAdmin):
    list_display = (
        "suggested_employee_id",
        "organization",
        "confidence",
        "reason",
        "status",
        "detected_at",
    )
    list_filter = ("status", "reason", "organization")
    search_fields = ("suggested_employee_id",)


@admin.register(RecognitionEvent)
class RecognitionEventAdmin(admin.ModelAdmin):
    list_display = ("kind", "status", "camera_name", "organization", "confidence", "detected_at")
    list_filter = ("kind", "status", "organization")
    search_fields = ("camera_name", "message")


@admin.register(CameraDwellSession)
class CameraDwellSessionAdmin(admin.ModelAdmin):
    list_display = ("employee", "camera", "seconds", "started_at", "ended_at")
    list_filter = ("camera", "organization")
    search_fields = ("employee__employee_id", "employee__first_name")
