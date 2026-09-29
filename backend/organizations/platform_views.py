from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Membership, Organization
from organizations.permissions import IsPlatformAdmin
from organizations.plans import PLAN_FREE, PLAN_LIMITS, PLAN_PRO, PLAN_STARTER, get_trial_days


class PlatformOrganizationSerializer(serializers.ModelSerializer):
    effective_plan = serializers.SerializerMethodField()
    people_count = serializers.IntegerField(read_only=True)
    camera_count = serializers.IntegerField(read_only=True)
    owner_email = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "org_type",
            "is_active",
            "plan",
            "effective_plan",
            "billing_exempt",
            "created_via",
            "subscription_status",
            "trial_ends_at",
            "people_count",
            "camera_count",
            "owner_email",
            "owner_name",
            "created_at",
        ]

    def get_effective_plan(self, obj):
        return obj.effective_plan()

    def get_owner_email(self, obj):
        owner = getattr(obj, "owner_membership", None)
        if owner is None:
            owner = obj.memberships.filter(role=Membership.ROLE_OWNER).select_related("user").first()
        if not owner:
            return ""
        return owner.user.email or owner.user.username

    def get_owner_name(self, obj):
        owner = getattr(obj, "owner_membership", None)
        if owner is None:
            owner = obj.memberships.filter(role=Membership.ROLE_OWNER).select_related("user").first()
        if not owner:
            return ""
        return f"{owner.user.first_name} {owner.user.last_name}".strip()


class PlatformCreateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    org_type = serializers.ChoiceField(
        choices=[Organization.TYPE_COMPANY, Organization.TYPE_SCHOOL],
        default=Organization.TYPE_COMPANY,
    )
    plan = serializers.ChoiceField(
        choices=[PLAN_FREE, PLAN_STARTER, PLAN_PRO],
        default=PLAN_STARTER,
    )
    billing_exempt = serializers.BooleanField(default=True)
    owner_email = serializers.EmailField()
    owner_password = serializers.CharField(write_only=True, min_length=8)
    owner_first_name = serializers.CharField(max_length=150)
    owner_last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate_owner_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists")
        return email


class PlatformUpdateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    is_active = serializers.BooleanField(required=False)
    plan = serializers.ChoiceField(choices=[PLAN_FREE, PLAN_STARTER, PLAN_PRO], required=False)
    billing_exempt = serializers.BooleanField(required=False)


def _org_queryset():
    return Organization.objects.annotate(
        people_count=Count("employees", distinct=True),
        camera_count=Count("cameras", distinct=True),
    ).order_by("-created_at")


class PlatformOrganizationListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        orgs = _org_queryset()
        return Response({
            "organizations": PlatformOrganizationSerializer(orgs, many=True).data,
            "plans": [{"id": key, **value} for key, value in PLAN_LIMITS.items()],
            "totals": {
                "organizations": orgs.count(),
                "active": orgs.filter(is_active=True).count(),
                "self_serve": orgs.filter(billing_exempt=False).count(),
                "complimentary": orgs.filter(billing_exempt=True).count(),
            },
        })

    def post(self, request):
        serializer = PlatformCreateOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        exempt = data.get("billing_exempt", True)
        org = Organization.objects.create(
            name=data["name"],
            org_type=data["org_type"],
            plan=data["plan"],
            billing_exempt=exempt,
            created_via="platform",
            subscription_status=(
                Organization.STATUS_ACTIVE if exempt else Organization.STATUS_TRIALING
            ),
            trial_ends_at=None if exempt else timezone.now() + timedelta(days=get_trial_days()),
        )
        owner = User.objects.create_user(
            username=data["owner_email"],
            email=data["owner_email"],
            password=data["owner_password"],
            first_name=data["owner_first_name"],
            last_name=data.get("owner_last_name") or "",
        )
        Membership.objects.create(
            user=owner,
            organization=org,
            role=Membership.ROLE_OWNER,
        )
        org = _org_queryset().get(pk=org.pk)
        return Response(
            PlatformOrganizationSerializer(org).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformOrganizationDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, pk):
        org = Organization.objects.filter(pk=pk).first()
        if not org:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = PlatformUpdateOrganizationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        update_fields = ["updated_at"]
        if "name" in data:
            org.name = data["name"]
            update_fields.append("name")
        if "is_active" in data:
            org.is_active = data["is_active"]
            update_fields.append("is_active")
        if "plan" in data:
            org.plan = data["plan"]
            update_fields.append("plan")
        if "billing_exempt" in data:
            org.billing_exempt = data["billing_exempt"]
            update_fields.append("billing_exempt")
            if data["billing_exempt"]:
                org.subscription_status = Organization.STATUS_ACTIVE
                update_fields.append("subscription_status")
        org.save(update_fields=update_fields)
        org = _org_queryset().get(pk=org.pk)
        return Response(PlatformOrganizationSerializer(org).data)


class PlatformDashboardView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.conf import settings
        from django.db.models import Sum
        from organizations.plans import limits_for

        orgs = _org_queryset()
        by_plan = list(
            Organization.objects.values("plan").annotate(total=Count("id")).order_by("plan")
        )
        people_total = orgs.aggregate(total=Sum("people_count"))["total"] or 0
        cameras_total = orgs.aggregate(total=Sum("camera_count"))["total"] or 0
        recent = orgs[:8]
        return Response({
            "totals": {
                "organizations": orgs.count(),
                "active": orgs.filter(is_active=True).count(),
                "self_serve": orgs.filter(billing_exempt=False).count(),
                "complimentary": orgs.filter(billing_exempt=True).count(),
                "people": people_total,
                "cameras": cameras_total,
            },
            "by_plan": by_plan,
            "plans": [{"id": key, **limits_for(key)} for key in PLAN_LIMITS],
            "recent": PlatformOrganizationSerializer(recent, many=True).data,
            "stripe_configured": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
        })


class PlatformPlansView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from organizations.plans import limits_for

        return Response({
            "plans": [{"id": key, **limits_for(key)} for key in PLAN_LIMITS],
        })

    def put(self, request):
        from organizations.models import PlatformConfig
        from organizations.plans import limits_for

        plans = request.data.get("plans")
        if not isinstance(plans, list):
            return Response({"error": "plans must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        overlay: dict = {}
        for item in plans:
            plan_id = item.get("id")
            if plan_id not in PLAN_LIMITS:
                continue
            overlay[plan_id] = {
                "label": str(item.get("label") or PLAN_LIMITS[plan_id]["label"]),
                "people": None if item.get("people") in (None, "", "unlimited") else int(item.get("people")),
                "cameras": int(item.get("cameras") or 0),
                "staff": None if item.get("staff") in (None, "", "unlimited") else int(item.get("staff")),
                "webhooks": bool(item.get("webhooks")),
                "api_key": bool(item.get("api_key")),
            }

        cfg = PlatformConfig.load()
        cfg.plan_limits = overlay
        cfg.save(update_fields=["plan_limits", "updated_at"])
        return Response({
            "plans": [{"id": key, **limits_for(key)} for key in PLAN_LIMITS],
        })


class PlatformSettingsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.conf import settings
        from organizations.models import PlatformConfig

        cfg = PlatformConfig.load()
        return Response({
            "trial_days": cfg.trial_days,
            "superadmin_email": request.user.email or request.user.username,
            "stripe_configured": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
            "frontend_url": getattr(settings, "FRONTEND_URL", ""),
        })

    def patch(self, request):
        from organizations.models import PlatformConfig

        cfg = PlatformConfig.load()
        if "trial_days" in request.data:
            days = int(request.data.get("trial_days") or 0)
            if days < 1 or days > 365:
                return Response({"error": "trial_days must be between 1 and 365"}, status=status.HTTP_400_BAD_REQUEST)
            cfg.trial_days = days
            cfg.save(update_fields=["trial_days", "updated_at"])

        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        if new_password:
            if not current_password or not request.user.check_password(current_password):
                return Response({"error": "Current password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
            if len(new_password) < 8:
                return Response({"error": "New password must be at least 8 characters"}, status=status.HTTP_400_BAD_REQUEST)
            request.user.set_password(new_password)
            request.user.save(update_fields=["password"])

        return self.get(request)

