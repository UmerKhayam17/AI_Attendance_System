from django.contrib.auth.models import User
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Department
from employees.serializers import DepartmentSerializer
from organizations.limits import ensure_branch_slot, ensure_staff_slot
from organizations.models import Branch, Invite, Membership, Shift
from organizations.permissions import CanView, IsOwner, IsOwnerOrAdmin
from organizations.query import parse_branch_id
from organizations.serializers import (
    BranchSerializer,
    IntegrationsSerializer,
    InviteCreateSerializer,
    InviteSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
    ShiftSerializer,
    user_payload,
)


class MeView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        return Response(
            user_payload(request.user, getattr(request, "membership", None))
        )


class OrganizationDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        return Response(OrganizationSerializer(request.organization).data)

    def patch(self, request):
        serializer = OrganizationUpdateSerializer(
            request.organization, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrganizationSerializer(request.organization).data)


class MemberListView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        members = Membership.objects.filter(
            organization=request.organization
        ).select_related("user")
        return Response(MembershipSerializer(members, many=True).data)


class MemberDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        membership = Membership.objects.filter(
            organization=request.organization, pk=pk
        ).select_related("user").first()
        if not membership:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        if membership.role == Membership.ROLE_OWNER:
            return Response(
                {"error": "Cannot change the owner role"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        role = request.data.get("role")
        allowed = {
            Membership.ROLE_ADMIN,
            Membership.ROLE_OPERATOR,
            Membership.ROLE_VIEWER,
        }
        if request.role != Membership.ROLE_OWNER:
            allowed.discard(Membership.ROLE_ADMIN)
        if role not in allowed:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)
        membership.role = role
        membership.save(update_fields=["role"])
        return Response(MembershipSerializer(membership).data)

    def delete(self, request, pk):
        membership = Membership.objects.filter(
            organization=request.organization, pk=pk
        ).first()
        if not membership:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        if membership.role == Membership.ROLE_OWNER:
            return Response(
                {"error": "Cannot remove the owner"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            request.role != Membership.ROLE_OWNER
            and membership.role == Membership.ROLE_ADMIN
        ):
            return Response(
                {"error": "Admins cannot remove other admins"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.user_id == request.user.id:
            return Response(
                {"error": "Cannot remove yourself"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InviteListView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        invites = Invite.objects.filter(
            organization=request.organization,
            accepted_at__isnull=True,
        )
        return Response(InviteSerializer(invites, many=True).data)

    def post(self, request):
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        role = serializer.validated_data["role"]

        if request.role != Membership.ROLE_OWNER and role == Membership.ROLE_ADMIN:
            return Response(
                {"error": "Only the owner can invite admins"},
                status=status.HTTP_403_FORBIDDEN,
            )

        ensure_staff_slot(request.organization)

        if Membership.objects.filter(
            organization=request.organization, user__email__iexact=email
        ).exists() or Membership.objects.filter(
            organization=request.organization, user__username__iexact=email
        ).exists():
            return Response(
                {"error": "That user is already a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username__iexact=email).exists():
            existing = User.objects.filter(username__iexact=email).first()
            if existing.memberships.exists():
                return Response(
                    {"error": "That email already belongs to another organization"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        Invite.objects.filter(
            organization=request.organization,
            email__iexact=email,
            accepted_at__isnull=True,
        ).delete()
        invite = Invite.issue(
            organization=request.organization,
            email=email,
            role=role,
            invited_by=request.user,
        )
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class InviteRevokeView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def delete(self, request, pk):
        invite = Invite.objects.filter(
            organization=request.organization, pk=pk, accepted_at__isnull=True
        ).first()
        if not invite:
            return Response({"error": "Invite not found"}, status=status.HTTP_404_NOT_FOUND)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IntegrationsView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        return Response(IntegrationsSerializer(request.organization).data)

    def patch(self, request):
        serializer = IntegrationsSerializer(
            request.organization,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "webhook_url" in data and data.get("webhook_url") and not request.organization.has_feature("webhooks"):
            return Response(
                {"error": "Webhooks require Starter or Pro"},
                status=status.HTTP_403_FORBIDDEN,
            )
        sms_on = data.get("notify_sms") or data.get("notify_whatsapp")
        if sms_on and not request.organization.limits().get("alerts"):
            return Response(
                {"error": "SMS / WhatsApp alerts require Starter or Pro"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer.save()
        return Response(IntegrationsSerializer(request.organization).data)


class RotateApiKeyView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        if not request.organization.has_feature("api_key"):
            return Response(
                {"error": "API keys require the Pro plan"},
                status=status.HTTP_403_FORBIDDEN,
            )
        request.organization.rotate_api_key()
        return Response(IntegrationsSerializer(request.organization).data)


def _shift_queryset(org, branch_id=None):
    qs = Shift.objects.filter(organization=org).annotate(employee_count=Count("employees"))
    if branch_id:
        qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
    return qs


class ShiftListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        branch_id = parse_branch_id(request)
        shifts = _shift_queryset(request.organization, branch_id)
        return Response(ShiftSerializer(shifts, many=True).data)

    def post(self, request):
        serializer = ShiftSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        has_default = Shift.objects.filter(organization=request.organization, is_default=True).exists()
        shift = serializer.save(
            organization=request.organization,
            is_default=serializer.validated_data.get("is_default", False) or not has_default,
        )
        shift = _shift_queryset(request.organization).get(pk=shift.pk)
        return Response(ShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class ShiftDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        shift = _shift_queryset(request.organization).filter(pk=pk).first()
        if not shift:
            return Response({"error": "Shift not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ShiftSerializer(shift, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if shift.is_default and serializer.validated_data.get("is_default") is False:
            other = Shift.objects.filter(organization=request.organization).exclude(pk=shift.pk).first()
            if not other:
                return Response(
                    {"error": "Keep at least one default shift"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer.save()
        shift = _shift_queryset(request.organization).get(pk=pk)
        return Response(ShiftSerializer(shift).data)

    def delete(self, request, pk):
        shift = Shift.objects.filter(organization=request.organization, pk=pk).first()
        if not shift:
            return Response({"error": "Shift not found"}, status=status.HTTP_404_NOT_FOUND)
        remaining = Shift.objects.filter(organization=request.organization).exclude(pk=pk)
        if not remaining.exists():
            return Response(
                {"error": "Create another shift before deleting the last one"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if shift.is_default:
            next_default = remaining.filter(is_active=True).first() or remaining.first()
            next_default.is_default = True
            next_default.save()
        else:
            next_default = remaining.filter(is_default=True).first() or remaining.first()
        shift.employees.update(shift=next_default)
        shift.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _department_queryset(org, branch_id=None):
    qs = Department.objects.filter(organization=org).select_related("branch").annotate(employee_count=Count("employees"))
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    return qs


class DepartmentListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        branch_id = parse_branch_id(request)
        rows = _department_queryset(request.organization, branch_id)
        return Response(DepartmentSerializer(rows, many=True).data)

    def post(self, request):
        serializer = DepartmentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        dept = serializer.save(organization=request.organization)
        if not dept.branch_id:
            dept.branch = request.organization.default_branch()
            dept.save(update_fields=["branch"])
        dept = _department_queryset(request.organization).get(pk=dept.pk)
        return Response(DepartmentSerializer(dept).data, status=status.HTTP_201_CREATED)


class DepartmentDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        dept = _department_queryset(request.organization).filter(pk=pk).first()
        if not dept:
            return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = DepartmentSerializer(dept, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        dept = _department_queryset(request.organization).get(pk=pk)
        return Response(DepartmentSerializer(dept).data)

    def delete(self, request, pk):
        dept = Department.objects.filter(organization=request.organization, pk=pk).first()
        if not dept:
            return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        if dept.employees.exists():
            return Response(
                {"error": "Reassign people before deleting this department"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dept.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _branch_queryset(org):
    return Branch.objects.filter(organization=org).select_related("manager").annotate(
        employee_count=Count("employees")
    )


class BranchListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        rows = _branch_queryset(request.organization)
        return Response(BranchSerializer(rows, many=True).data)

    def post(self, request):
        ensure_branch_slot(request.organization)
        serializer = BranchSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        has_default = Branch.objects.filter(organization=request.organization, is_default=True).exists()
        branch = serializer.save(
            organization=request.organization,
            is_default=serializer.validated_data.get("is_default", False) or not has_default,
        )
        if not branch.timezone:
            branch.timezone = request.organization.timezone
            branch.save(update_fields=["timezone"])
        branch = _branch_queryset(request.organization).get(pk=branch.pk)
        return Response(BranchSerializer(branch).data, status=status.HTTP_201_CREATED)


class BranchDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        branch = _branch_queryset(request.organization).filter(pk=pk).first()
        if not branch:
            return Response({"error": "Branch not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = BranchSerializer(branch, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if branch.is_default and serializer.validated_data.get("is_default") is False:
            other = Branch.objects.filter(organization=request.organization).exclude(pk=branch.pk).first()
            if not other:
                return Response(
                    {"error": "Keep at least one default branch"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer.save()
        branch = _branch_queryset(request.organization).get(pk=pk)
        return Response(BranchSerializer(branch).data)

    def delete(self, request, pk):
        branch = Branch.objects.filter(organization=request.organization, pk=pk).first()
        if not branch:
            return Response({"error": "Branch not found"}, status=status.HTTP_404_NOT_FOUND)
        remaining = Branch.objects.filter(organization=request.organization).exclude(pk=pk)
        if not remaining.exists():
            return Response(
                {"error": "Create another branch before deleting the last one"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if branch.employees.exists() or branch.departments.exists() or branch.cameras.exists():
            return Response(
                {"error": "Reassign people, departments, and cameras before deleting this branch"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if branch.is_default:
            next_default = remaining.filter(is_active=True).first() or remaining.first()
            next_default.is_default = True
            next_default.save()
        branch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
