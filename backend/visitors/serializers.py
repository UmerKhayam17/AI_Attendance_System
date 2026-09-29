from rest_framework import serializers

from employees.models import Employee
from organizations.models import Branch
from visitors.models import Visit, Visitor


class VisitorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    visit_count = serializers.IntegerField(read_only=True, required=False)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Visitor
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "email",
            "company",
            "id_type",
            "id_number",
            "photo",
            "photo_url",
            "notes",
            "is_blacklisted",
            "blacklist_reason",
            "visit_count",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"photo": {"write_only": True, "required": False}}

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return obj.photo.url if hasattr(obj.photo, "url") else ""


class VisitSerializer(serializers.ModelSerializer):
    visitor_detail = VisitorSerializer(source="visitor", read_only=True)
    host_name = serializers.SerializerMethodField()
    host_employee_id = serializers.CharField(source="host.employee_id", read_only=True, default=None)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    purpose_label = serializers.CharField(source="get_purpose_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    gate_path = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = [
            "id",
            "visitor",
            "visitor_detail",
            "host",
            "host_name",
            "host_employee_id",
            "branch",
            "branch_name",
            "purpose",
            "purpose_label",
            "status",
            "status_label",
            "source",
            "expected_at",
            "expected_end",
            "check_in_at",
            "check_out_at",
            "badge_code",
            "vehicle_plate",
            "notes",
            "public_token",
            "denied_reason",
            "gate_path",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "check_in_at",
            "check_out_at",
            "badge_code",
            "public_token",
            "denied_reason",
        ]

    def get_host_name(self, obj):
        if not obj.host:
            return ""
        return f"{obj.host.first_name} {obj.host.last_name}".strip()

    def get_gate_path(self, obj):
        return f"/gate/{obj.public_token}"

    def validate_host(self, host):
        if host is None:
            return host
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and host.organization_id != org.id:
            raise serializers.ValidationError("Host is not in this organization")
        return host

    def validate_branch(self, branch):
        if branch is None:
            return branch
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and branch.organization_id != org.id:
            raise serializers.ValidationError("Branch is not in this organization")
        return branch


class VisitWriteSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    company = serializers.CharField(required=False, allow_blank=True)
    id_type = serializers.ChoiceField(choices=Visitor.ID_CHOICES, required=False)
    id_number = serializers.CharField(required=False, allow_blank=True)
    visitor = serializers.IntegerField(required=False)
    host = serializers.IntegerField(required=False, allow_null=True)
    branch = serializers.IntegerField(required=False, allow_null=True)
    purpose = serializers.ChoiceField(choices=Visit.PURPOSE_CHOICES, required=False)
    source = serializers.ChoiceField(choices=Visit.SOURCE_CHOICES, required=False)
    expected_at = serializers.DateTimeField(required=False, allow_null=True)
    expected_end = serializers.DateTimeField(required=False, allow_null=True)
    vehicle_plate = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    check_in_now = serializers.BooleanField(required=False, default=False)

    def create_visit(self, organization, user=None):
        from visitors.services import check_in, create_visit, find_or_create_visitor

        data = dict(self.validated_data)
        visitor_id = data.pop("visitor", None)
        host_id = data.pop("host", None)
        branch_id = data.pop("branch", None)
        check_in_now = data.pop("check_in_now", False)
        visitor = None
        if visitor_id:
            visitor = Visitor.objects.filter(organization=organization, pk=visitor_id).first()
            if visitor is None:
                raise serializers.ValidationError({"visitor": "Visitor not found"})
        host = None
        if host_id:
            host = Employee.objects.filter(organization=organization, pk=host_id, is_active=True).first()
            if host is None:
                raise serializers.ValidationError({"host": "Host not found"})
        branch = None
        if branch_id:
            branch = Branch.objects.filter(organization=organization, pk=branch_id).first()
        if visitor is None:
            visitor = find_or_create_visitor(organization, data)
        visit = create_visit(
            organization,
            {
                "visitor": visitor,
                "host": host,
                "branch": branch,
                **data,
            },
            user=user,
        )
        if check_in_now:
            visit = check_in(visit)
        return visit


class PublicVisitSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source="visitor.full_name", read_only=True)
    visitor_company = serializers.CharField(source="visitor.company", read_only=True)
    host_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    purpose_label = serializers.CharField(source="get_purpose_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)

    class Meta:
        model = Visit
        fields = [
            "visitor_name",
            "visitor_company",
            "host_name",
            "organization_name",
            "purpose_label",
            "status",
            "status_label",
            "expected_at",
            "expected_end",
            "check_in_at",
            "badge_code",
            "branch_name",
        ]

    def get_host_name(self, obj):
        if not obj.host:
            return ""
        return f"{obj.host.first_name} {obj.host.last_name}".strip()
