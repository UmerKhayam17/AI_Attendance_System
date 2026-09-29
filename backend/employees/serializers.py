from rest_framework import serializers

from employees.models import Department, Employee, EmployeeDocument
from organizations.models import Branch, Shift
from recognition.models import FaceEnrollment


class FaceEnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceEnrollment
        fields = [
            "id",
            "is_enrolled",
            "is_trained",
            "total_images",
            "model_version",
            "dataset_folder",
            "profile_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True, required=False)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "branch",
            "branch_name",
            "is_active",
            "sort_order",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "branch_name", "employee_count", "created_at", "updated_at"]

    def validate_branch(self, branch):
        if branch is None:
            return branch
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and branch.organization_id != org.id:
            raise serializers.ValidationError("Branch is not in this organization")
        return branch

    def validate(self, attrs):
        name = (attrs.get("name") if "name" in attrs else getattr(self.instance, "name", "") or "").strip()
        if "name" in attrs:
            attrs["name"] = name
        if not name:
            raise serializers.ValidationError({"name": "Name is required"})
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org is None and self.instance is not None:
            org = self.instance.organization
        branch = attrs.get("branch") if "branch" in attrs else getattr(self.instance, "branch", None)
        if org:
            qs = Department.objects.filter(organization=org, name__iexact=name, branch=branch)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"name": "A department with this name already exists in this branch"})
        return attrs


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = ["id", "title", "category", "file", "file_url", "uploaded_at"]
        read_only_fields = ["id", "file_url", "uploaded_at"]
        extra_kwargs = {"file": {"write_only": False}}

    def get_file_url(self, obj):
        if not obj.file:
            return ""
        return obj.file.url if hasattr(obj.file, "url") else ""


EMPLOYEE_WRITE_FIELDS = [
    "employee_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "national_id",
    "date_of_birth",
    "gender",
    "address",
    "guardian_name",
    "guardian_phone",
    "guardian_email",
    "branch",
    "department",
    "designation",
    "employment_type",
    "joining_date",
    "manager",
    "shift",
    "is_active",
]


class EmployeeSerializer(serializers.ModelSerializer):
    face_enrollment = FaceEnrollmentSerializer(read_only=True)
    shift = serializers.PrimaryKeyRelatedField(
        queryset=Shift.objects.all(),
        allow_null=True,
        required=False,
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        allow_null=True,
        required=False,
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        allow_null=True,
        required=False,
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        allow_null=True,
        required=False,
    )
    shift_detail = serializers.SerializerMethodField()
    department_name = serializers.CharField(read_only=True)
    branch_name = serializers.CharField(read_only=True)
    manager_name = serializers.SerializerMethodField()
    has_portal_login = serializers.SerializerMethodField()
    document_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Employee
        fields = [
            "id",
            *EMPLOYEE_WRITE_FIELDS,
            "department_name",
            "branch_name",
            "manager_name",
            "shift_detail",
            "has_portal_login",
            "face_enrollment",
            "document_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "face_enrollment",
            "shift_detail",
            "department_name",
            "branch_name",
            "manager_name",
            "has_portal_login",
            "document_count",
        ]

    def get_has_portal_login(self, obj):
        return bool(obj.user_id)

    def get_manager_name(self, obj):
        if not obj.manager_id:
            return ""
        return obj.manager.display_name

    def get_shift_detail(self, obj):
        shift = obj.shift
        if not shift:
            return None
        return {
            "id": shift.id,
            "name": shift.name,
            "kind": getattr(shift, "kind", "fixed"),
            "start_time": shift.start_time.strftime("%H:%M:%S") if shift.start_time else None,
            "late_after": shift.late_after.strftime("%H:%M:%S") if shift.late_after else None,
            "end_time": shift.end_time.strftime("%H:%M:%S") if shift.end_time else None,
            "is_default": shift.is_default,
            "is_active": shift.is_active,
        }

    def validate(self, attrs):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        branch = attrs.get("branch") if "branch" in attrs else getattr(self.instance, "branch", None)
        department = attrs.get("department") if "department" in attrs else getattr(self.instance, "department", None)
        manager = attrs.get("manager") if "manager" in attrs else getattr(self.instance, "manager", None)
        if department and branch and department.branch_id and department.branch_id != branch.id:
            raise serializers.ValidationError({"department": "Department is not in this branch"})
        if manager and self.instance and manager.pk == self.instance.pk:
            raise serializers.ValidationError({"manager": "An employee cannot manage themselves"})
        if manager and org and manager.organization_id != org.id:
            raise serializers.ValidationError({"manager": "Manager is not in this organization"})
        return attrs

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org:
            self.fields["shift"].queryset = Shift.objects.filter(organization=org)
            self.fields["department"].queryset = Department.objects.filter(organization=org)
            self.fields["branch"].queryset = Branch.objects.filter(organization=org)
            self.fields["manager"].queryset = Employee.objects.filter(organization=org)


class EmployeeCreateSerializer(EmployeeSerializer):
    class Meta(EmployeeSerializer.Meta):
        fields = EMPLOYEE_WRITE_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org:
            self.fields["shift"].queryset = Shift.objects.filter(organization=org, is_active=True)
            self.fields["department"].queryset = Department.objects.filter(organization=org, is_active=True)
            self.fields["branch"].queryset = Branch.objects.filter(organization=org, is_active=True)
            self.fields["manager"].queryset = Employee.objects.filter(organization=org, is_active=True)
