from rest_framework import serializers

from recognition.models import Camera, DetectionSnapshot, FaceEnrollment, MatchReview, RecognitionEvent
from recognition.services.camera_health import health_from_runtime
from recognition.services.snapshot_saver import snapshot_to_dict


class CameraSerializer(serializers.ModelSerializer):
    runtime = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    health = serializers.SerializerMethodField()

    class Meta:
        model = Camera
        fields = [
            "id",
            "name",
            "location",
            "branch",
            "branch_name",
            "rtsp_url",
            "zone",
            "is_active",
            "sort_order",
            "health",
            "health_status",
            "last_heartbeat_at",
            "last_error",
            "fps",
            "runtime",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "rtsp_url": {"write_only": False},
            "health_status": {"read_only": True},
            "last_heartbeat_at": {"read_only": True},
            "last_error": {"read_only": True},
            "fps": {"read_only": True},
        }

    def validate_branch(self, branch):
        if branch is None:
            return branch
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and branch.organization_id != org.id:
            raise serializers.ValidationError("Branch is not in this organization")
        return branch

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = getattr(request, "role", None) if request else None
        if role not in ("owner", "admin"):
            data.pop("rtsp_url", None)
        return data

    def get_runtime(self, obj):
        manager = self.context.get("cctv_manager")
        if not manager:
            return None
        return manager.get_status(obj.id)

    def get_health(self, obj):
        return health_from_runtime(self.get_runtime(obj), obj)


class FaceEnrollmentDetailSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    embeddings_count = serializers.SerializerMethodField()

    class Meta:
        model = FaceEnrollment
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "is_enrolled",
            "is_trained",
            "total_images",
            "model_version",
            "dataset_folder",
            "profile_image",
            "embeddings_count",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_embeddings_count(self, obj):
        raw = obj.embeddings
        if isinstance(raw, list) and raw:
            if isinstance(raw[0], (int, float)):
                return 1
            return len(raw)
        return 1 if obj.embedding else 0


class CaptureImageSerializer(serializers.Serializer):
    image = serializers.CharField(help_text="Base64-encoded JPEG image")


class IdentifySerializer(serializers.Serializer):
    image = serializers.CharField(help_text="Base64-encoded JPEG image from CCTV/webcam")
    mark_attendance = serializers.BooleanField(default=False)
    source = serializers.ChoiceField(
        choices=["cctv", "webcam", "manual", "mobile"],
        default="cctv",
    )
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)


class DetectionSnapshotSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    camera_label = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DetectionSnapshot
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "camera_id",
            "camera_name",
            "camera_label",
            "image_url",
            "confidence",
            "attendance_action",
            "detected_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_camera_label(self, obj):
        return f"Camera #{obj.camera_id or '?'} · {obj.camera_name}"

    def get_image_url(self, obj):
        return snapshot_to_dict(obj)["image_url"]


class MatchReviewSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True, default=None)
    employee_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    reviewed_by_email = serializers.SerializerMethodField()

    class Meta:
        model = MatchReview
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "suggested_employee_id",
            "camera_id",
            "camera_name",
            "image_url",
            "confidence",
            "second_best",
            "reason",
            "status",
            "track_id",
            "source",
            "notes",
            "reviewed_by_email",
            "reviewed_at",
            "attendance_action",
            "detected_at",
        ]

    def get_employee_name(self, obj):
        if not obj.employee:
            return obj.suggested_employee_id or ""
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        return f"{obj.image.url}" if hasattr(obj.image, "url") else ""

    def get_reviewed_by_email(self, obj):
        user = obj.reviewed_by
        if not user:
            return None
        return user.email or user.username


class RecognitionEventSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True, default=None)
    employee_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    camera_id = serializers.IntegerField(source="camera.id", read_only=True, default=None)

    class Meta:
        model = RecognitionEvent
        fields = [
            "id",
            "kind",
            "status",
            "employee_id",
            "employee_name",
            "camera_id",
            "camera_name",
            "confidence",
            "message",
            "extra",
            "image_url",
            "track_id",
            "source",
            "attendance_action",
            "detected_at",
        ]

    def get_employee_name(self, obj):
        if not obj.employee:
            return ""
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        return obj.image.url if hasattr(obj.image, "url") else ""
