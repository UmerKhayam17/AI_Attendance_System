from rest_framework import serializers

from attendance.models import (
    AttendanceCorrection,
    AttendanceRecord,
    Holiday,
    LeaveRequest,
    LeaveType,
    OvertimeRequest,
)
from employees.models import Employee


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "date",
            "check_in",
            "check_out",
            "status",
            "check_in_confidence",
            "check_out_confidence",
            "source",
            "latitude",
            "longitude",
            "notes",
            "overtime_minutes",
            "early_leave",
            "missing_checkout",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class ManualAttendanceSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    action = serializers.ChoiceField(choices=["check_in", "check_out"])
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class HolidaySerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)

    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "repeats_yearly", "branch", "branch_name", "created_at"]
        read_only_fields = ["id", "branch_name", "created_at"]

    def validate_branch(self, branch):
        if branch is None:
            return branch
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and branch.organization_id != org.id:
            raise serializers.ValidationError("Branch is not in this organization")
        return branch


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    decided_by_email = serializers.SerializerMethodField()
    leave_type = serializers.CharField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "status",
            "reason",
            "decided_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee_id",
            "employee_name",
            "status",
            "decided_by_email",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_decided_by_email(self, obj):
        user = obj.decided_by
        if not user:
            return None
        return user.email or user.username

    def validate_leave_type(self, value):
        code = (value or "").strip().lower()
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org:
            from attendance.leave_types import active_leave_types

            allowed = {row.code for row in active_leave_types(org)}
            if allowed and code not in allowed:
                raise serializers.ValidationError("Unknown leave type")
        return code or LeaveRequest.TYPE_ANNUAL

    def validate(self, attrs):
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and end < start:
            raise serializers.ValidationError("End date must be on or after start date")
        return attrs

    def validate_employee(self, employee: Employee):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and employee.organization_id != org.id:
            raise serializers.ValidationError("Employee is not in this organization")
        return employee


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id",
            "code",
            "name",
            "paid",
            "entitlement_days",
            "requires_document",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id"]

    def validate_code(self, value):
        return (value or "").strip().lower().replace(" ", "_")


class AttendanceCorrectionSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    decided_by_email = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "date",
            "requested_check_in",
            "requested_check_out",
            "original_check_in",
            "original_check_out",
            "original_status",
            "reason",
            "status",
            "decided_by_email",
            "applied_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "employee_id",
            "employee_name",
            "original_check_in",
            "original_check_out",
            "original_status",
            "status",
            "decided_by_email",
            "applied_at",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name

    def get_decided_by_email(self, obj):
        return (obj.decided_by.email or obj.decided_by.username) if obj.decided_by_id else None

    def validate_employee(self, employee: Employee):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and employee.organization_id != org.id:
            raise serializers.ValidationError("Employee is not in this organization")
        return employee

    def validate(self, attrs):
        if not attrs.get("requested_check_in") and not attrs.get("requested_check_out"):
            if not getattr(self.instance, "requested_check_in", None) and not getattr(
                self.instance, "requested_check_out", None
            ):
                raise serializers.ValidationError("Provide a check-in and/or check-out time")
        return attrs


class OvertimeRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    decided_by_email = serializers.SerializerMethodField()

    class Meta:
        model = OvertimeRequest
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "date",
            "minutes",
            "reason",
            "source",
            "status",
            "decided_by_email",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "employee_id",
            "employee_name",
            "source",
            "status",
            "decided_by_email",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name

    def get_decided_by_email(self, obj):
        return (obj.decided_by.email or obj.decided_by.username) if obj.decided_by_id else None

    def validate_employee(self, employee: Employee):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and employee.organization_id != org.id:
            raise serializers.ValidationError("Employee is not in this organization")
        return employee

