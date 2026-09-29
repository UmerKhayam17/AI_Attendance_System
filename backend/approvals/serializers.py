from rest_framework import serializers

from approvals.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStep,
    ApprovalWorkflow,
    AuditEvent,
    InAppNotification,
)


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStep
        fields = ["id", "order", "assignee_role"]
        read_only_fields = ["id"]


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True)

    class Meta:
        model = ApprovalWorkflow
        fields = ["id", "kind", "is_active", "steps", "updated_at"]
        read_only_fields = ["id", "kind", "updated_at"]

    def update(self, instance, validated_data):
        steps = validated_data.pop("steps", None)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()
        if steps is not None:
            if not steps:
                raise serializers.ValidationError({"steps": "At least one step is required"})
            instance.steps.all().delete()
            for index, payload in enumerate(steps, start=1):
                ApprovalStep.objects.create(
                    workflow=instance,
                    order=payload.get("order") or index,
                    assignee_role=payload.get("assignee_role") or ApprovalStep.ROLE_ADMIN,
                )
        return instance


class ApprovalActionSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalAction
        fields = ["id", "action", "comment", "created_at", "actor_email"]

    def get_actor_email(self, obj):
        if not obj.actor_id:
            return None
        return obj.actor.email or obj.actor.username


class ApprovalRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    submitted_by_email = serializers.SerializerMethodField()
    current_step_role = serializers.CharField(source="current_step.assignee_role", read_only=True, default=None)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    actions = ApprovalActionSerializer(many=True, read_only=True)
    can_act = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "kind",
            "kind_label",
            "target_id",
            "employee",
            "employee_id",
            "employee_name",
            "status",
            "current_step_role",
            "submitted_by_email",
            "can_act",
            "actions",
            "created_at",
            "updated_at",
            "decided_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name

    def get_submitted_by_email(self, obj):
        if not obj.submitted_by_id:
            return None
        return obj.submitted_by.email or obj.submitted_by.username

    def get_can_act(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return False
        from approvals.engine import can_act

        return can_act(request.user, obj, obj.current_step)


class InAppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InAppNotification
        fields = ["id", "kind", "title", "body", "link", "read_at", "created_at"]


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "action",
            "model",
            "object_id",
            "old_value",
            "new_value",
            "reason",
            "ip_address",
            "actor_email",
            "created_at",
        ]

    def get_actor_email(self, obj):
        if not obj.actor_id:
            return None
        return obj.actor.email or obj.actor.username
