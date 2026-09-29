from django.contrib.auth.models import User
from rest_framework import serializers

from organizations.models import Branch, Invite, Membership, Organization, Shift, ShiftAssignment
from organizations.plans import PLAN_LIMITS


class OrganizationSerializer(serializers.ModelSerializer):
    effective_plan = serializers.SerializerMethodField()
    limits = serializers.SerializerMethodField()
    trial_active = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "org_type",
            "timezone",
            "work_start",
            "late_after",
            "weekend_days",
            "is_active",
            "plan",
            "effective_plan",
            "subscription_status",
            "current_period_end",
            "trial_ends_at",
            "trial_active",
            "limits",
            "features",
            "billing_exempt",
            "created_via",
            "webhook_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "is_active",
            "plan",
            "effective_plan",
            "subscription_status",
            "current_period_end",
            "trial_ends_at",
            "trial_active",
            "limits",
            "features",
            "billing_exempt",
            "created_via",
            "created_at",
            "updated_at",
        ]

    def get_effective_plan(self, obj):
        return obj.effective_plan()

    def get_limits(self, obj):
        return obj.limits()

    def get_trial_active(self, obj):
        if obj.billing_exempt:
            return False
        return obj.subscription_status == Organization.STATUS_TRIALING and obj.effective_plan() != "free"

    def get_features(self, obj):
        limits = obj.limits()
        return {
            "webhooks": bool(limits.get("webhooks")),
            "api_key": bool(limits.get("api_key")),
            "cctv": bool(limits.get("cameras")),
            "alerts": bool(limits.get("alerts")),
            "exports": bool(limits.get("exports")),
            "self_service": bool(limits.get("self_service", True)),
        }


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "name",
            "org_type",
            "timezone",
            "work_start",
            "late_after",
            "weekend_days",
        ]

    def validate_weekend_days(self, value):
        return _validate_weekend_days(value)


def _validate_weekend_days(value):
    if value in (None, ""):
        return [5, 6]
    if not isinstance(value, list):
        raise serializers.ValidationError("weekend_days must be a list")
    days = []
    for item in value:
        try:
            n = int(item)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError("Weekdays must be integers 0–6") from exc
        if n < 0 or n > 6:
            raise serializers.ValidationError("Weekdays must be 0–6 (Mon–Sun)")
        if n not in days:
            days.append(n)
    return days


class BranchSerializer(serializers.ModelSerializer):
    manager_email = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "latitude",
            "longitude",
            "geofence_radius_m",
            "timezone",
            "weekend_days",
            "manager",
            "manager_email",
            "is_default",
            "is_active",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "manager_email", "employee_count", "created_at", "updated_at"]

    def get_manager_email(self, obj):
        user = obj.manager
        if not user:
            return None
        return user.email or user.username

    def validate_weekend_days(self, value):
        return _validate_weekend_days(value)

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Name is required")
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org is None and self.instance is not None:
            org = self.instance.organization
        if org:
            qs = Branch.objects.filter(organization=org, name__iexact=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A branch with this name already exists")
        return name

    def validate_manager(self, user):
        if user is None:
            return user
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and not Membership.objects.filter(organization=org, user=user).exists():
            raise serializers.ValidationError("Manager must be a member of this organization")
        return user


class IntegrationsSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(read_only=True)
    can_use_webhooks = serializers.SerializerMethodField()
    can_use_api_key = serializers.SerializerMethodField()
    can_use_alerts = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "webhook_url",
            "webhook_secret",
            "api_key",
            "can_use_webhooks",
            "can_use_api_key",
            "can_use_alerts",
            "notify_late",
            "notify_absent",
            "notify_email",
            "notify_sms",
            "notify_whatsapp",
            "twilio_account_sid",
            "twilio_auth_token",
            "twilio_from_number",
            "twilio_whatsapp_from",
        ]
        extra_kwargs = {
            "twilio_auth_token": {"write_only": False},
        }

    def get_can_use_webhooks(self, obj):
        return obj.has_feature("webhooks")

    def get_can_use_api_key(self, obj):
        return obj.has_feature("api_key")

    def get_can_use_alerts(self, obj):
        return bool(obj.limits().get("alerts"))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        token = data.get("twilio_auth_token") or ""
        if token:
            data["twilio_auth_token"] = "••••" + token[-4:] if len(token) > 4 else "••••"
        return data

    def update(self, instance, validated_data):
        token = validated_data.get("twilio_auth_token")
        if token and token.startswith("••••"):
            validated_data.pop("twilio_auth_token", None)
        return super().update(instance, validated_data)


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "created_at",
        ]
        read_only_fields = ["id", "user_id", "created_at"]


class InviteSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)
    invite_url = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True, default=None)

    class Meta:
        model = Invite
        fields = [
            "id",
            "email",
            "role",
            "token",
            "invited_by_email",
            "accepted_at",
            "expires_at",
            "created_at",
            "invite_url",
            "employee_id",
        ]
        read_only_fields = fields

    def get_invite_url(self, obj):
        from django.conf import settings

        base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        return f"{base}/accept-invite?token={obj.token}"


class ShiftSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True, required=False)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)

    class Meta:
        model = Shift
        fields = [
            "id",
            "name",
            "kind",
            "branch",
            "branch_name",
            "start_time",
            "late_after",
            "end_time",
            "required_hours",
            "break_start",
            "break_end",
            "second_start",
            "second_end",
            "grace_minutes",
            "early_leave_grace_minutes",
            "overtime_grace_minutes",
            "is_default",
            "is_active",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "branch_name", "employee_count", "created_at", "updated_at"]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Name is required")
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org is None and self.instance is not None:
            org = self.instance.organization
        if org:
            qs = Shift.objects.filter(organization=org, name__iexact=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A shift with this name already exists")
        return name

    def validate_branch(self, branch):
        if branch is None:
            return branch
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org and branch.organization_id != org.id:
            raise serializers.ValidationError("Branch is not in this organization")
        return branch


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source="shift.name", read_only=True)

    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "shift",
            "shift_name",
            "start_date",
            "end_date",
            "weekdays",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "shift_name", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and end < start:
            raise serializers.ValidationError("End date must be on or after start date")
        return attrs


class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            Membership.ROLE_ADMIN,
            Membership.ROLE_OPERATOR,
            Membership.ROLE_VIEWER,
        ]
    )


class PlanCatalogSerializer(serializers.Serializer):
    def to_representation(self, _instance):
        return [
            {"id": key, **value}
            for key, value in PLAN_LIMITS.items()
        ]


def user_payload(user: User, membership: Membership | None = None) -> dict:
    is_superadmin = bool(user.is_superuser)
    org = None if is_superadmin else (membership.organization if membership else None)
    role = "superadmin" if is_superadmin else (membership.role if membership else None)
    portal_people = []
    if org and Membership.is_portal_role(role):
        from employees.access import portal_employees_qs

        for emp in portal_employees_qs(user, org, role):
            portal_people.append({
                "id": emp.id,
                "employee_id": emp.employee_id,
                "name": emp.display_name,
            })
    return {
        "id": user.id,
        "email": user.email or user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": role,
        "is_superadmin": is_superadmin,
        "organization": OrganizationSerializer(org).data if org else None,
        "portal_people": portal_people,
    }
