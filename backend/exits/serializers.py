from rest_framework import serializers

from employees.models import Employee
from exits.models import ExitCase, ExitChecklistTemplate, ExitClearanceItem, ExitPolicy


class ExitPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitPolicy
        fields = [
            "notice_period_days",
            "probation_notice_days",
            "require_clearance",
            "require_interview",
            "auto_deactivate",
            "allow_notice_buyout",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class ExitChecklistTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitChecklistTemplate
        fields = ["id", "category", "title", "sort_order", "is_active"]
        read_only_fields = ["id"]


class ExitClearanceItemSerializer(serializers.ModelSerializer):
    cleared_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ExitClearanceItem
        fields = [
            "id",
            "category",
            "title",
            "is_cleared",
            "notes",
            "cleared_by_email",
            "cleared_at",
            "sort_order",
        ]
        read_only_fields = ["id", "category", "title", "cleared_by_email", "cleared_at", "sort_order"]

    def get_cleared_by_email(self, obj):
        return obj.cleared_by.email if obj.cleared_by_id else None


class ExitCaseSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    department = serializers.CharField(source="employee.department_name", read_only=True)
    initiated_by_email = serializers.SerializerMethodField()
    checklist_items = ExitClearanceItemSerializer(many=True, read_only=True)
    clearance_done = serializers.BooleanField(read_only=True)
    notice_shortfall_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExitCase
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "department",
            "exit_type",
            "status",
            "resignation_date",
            "last_working_day",
            "notice_period_days",
            "notice_buyout_days",
            "notice_shortfall_days",
            "reason",
            "handover_notes",
            "interview_notes",
            "interview_completed",
            "rehire_eligible",
            "clearance_done",
            "checklist_items",
            "initiated_by_email",
            "final_settlement_notes",
            "last_payroll_run",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "department",
            "status",
            "clearance_done",
            "notice_shortfall_days",
            "checklist_items",
            "initiated_by_email",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name

    def get_initiated_by_email(self, obj):
        return obj.initiated_by.email if obj.initiated_by_id else None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org:
            self.fields["employee"].queryset = Employee.objects.filter(organization=org)


class ExitCaseWriteSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.none())
    exit_type = serializers.ChoiceField(choices=ExitCase.TYPE_CHOICES, required=False)
    resignation_date = serializers.DateField(required=False)
    last_working_day = serializers.DateField(required=False)
    notice_period_days = serializers.IntegerField(required=False, min_value=0)
    notice_buyout_days = serializers.IntegerField(required=False, min_value=0)
    reason = serializers.CharField(required=False, allow_blank=True)
    handover_notes = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org:
            self.fields["employee"].queryset = Employee.objects.filter(organization=org, is_active=True)
