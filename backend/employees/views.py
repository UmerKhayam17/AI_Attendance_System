from pathlib import Path

from django.conf import settings
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from employees.models import Employee, EmployeeDocument
from employees.serializers import (
    EmployeeCreateSerializer,
    EmployeeDocumentSerializer,
    EmployeeSerializer,
)
from organizations.limits import ensure_person_slot
from organizations.mixins import OrganizationScopedMixin
from organizations.models import Invite, Membership, ShiftAssignment
from organizations.permissions import CanView, IsOwnerOrAdmin
from organizations.query import parse_branch_id
from organizations.serializers import InviteSerializer, ShiftAssignmentSerializer
from recognition.models import FaceEnrollment


class EmployeeViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Employee.objects.select_related(
        "shift", "face_enrollment", "user", "department", "branch", "manager"
    ).annotate(document_count=Count("documents")).order_by("-created_at")
    lookup_field = "employee_id"
    organization_field = "organization"
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "documents", "shift_assignments"):
            if self.request.method in ("GET", "HEAD", "OPTIONS"):
                return [CanView()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        branch_id = parse_branch_id(self.request)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = request.organization
        ensure_person_slot(org)
        employee = serializer.save(organization=org)
        if not employee.branch_id:
            employee.branch = org.default_branch()
            employee.save(update_fields=["branch"])
        if employee.shift_id is None:
            default = org.default_shift(employee.branch)
            if default:
                employee.shift = default
                employee.save(update_fields=["shift"])

        dataset_folder = f"org_{org.id}/dataset/{employee.employee_id}"
        folder_path = Path(settings.MEDIA_ROOT) / dataset_folder
        folder_path.mkdir(parents=True, exist_ok=True)

        FaceEnrollment.objects.create(
            employee=employee,
            dataset_folder=dataset_folder,
        )

        output = EmployeeSerializer(employee, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        employee = serializer.save()
        if employee.shift_id is None:
            default = self.request.organization.default_shift(employee.branch)
            if default:
                employee.shift = default
                employee.save(update_fields=["shift"])

    @action(detail=True, methods=["post"])
    def deactivate(self, request, employee_id=None):
        employee = self.get_object()
        employee.is_active = False
        employee.save(update_fields=["is_active", "updated_at"])
        return Response(EmployeeSerializer(employee).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, employee_id=None):
        employee = self.get_object()
        employee.is_active = True
        employee.save(update_fields=["is_active", "updated_at"])
        return Response(EmployeeSerializer(employee).data)

    @action(detail=True, methods=["post"], url_path="invite-portal")
    def invite_portal(self, request, employee_id=None):
        employee = self.get_object()
        role = (request.data.get("role") or Membership.ROLE_EMPLOYEE).strip()
        if role not in Membership.PORTAL_ROLES:
            return Response({"error": "Role must be employee or parent"}, status=status.HTTP_400_BAD_REQUEST)
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            email = (employee.email if role == Membership.ROLE_EMPLOYEE else employee.guardian_email) or ""
            email = email.lower().strip()
        if not email:
            return Response(
                {"error": "Provide an email, or set the person / guardian email first"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Membership.objects.filter(organization=request.organization, user__email__iexact=email).exists():
            return Response({"error": "That email already has a login"}, status=status.HTTP_400_BAD_REQUEST)
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
            employee=employee,
        )
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="documents")
    def documents(self, request, employee_id=None):
        employee = self.get_object()
        if request.method == "GET":
            rows = employee.documents.all()
            return Response(EmployeeDocumentSerializer(rows, many=True).data)
        serializer = EmployeeDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(employee=employee)
        return Response(EmployeeDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<doc_id>[0-9]+)")
    def delete_document(self, request, employee_id=None, doc_id=None):
        employee = self.get_object()
        doc = EmployeeDocument.objects.filter(employee=employee, pk=doc_id).first()
        if not doc:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="shift-assignments")
    def shift_assignments(self, request, employee_id=None):
        employee = self.get_object()
        if request.method == "GET":
            rows = employee.shift_assignments.select_related("shift")
            return Response(ShiftAssignmentSerializer(rows, many=True).data)
        serializer = ShiftAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = serializer.validated_data["shift"]
        if shift.organization_id != request.organization.id:
            return Response({"error": "Shift is not in this organization"}, status=status.HTTP_400_BAD_REQUEST)
        assignment = serializer.save(employee=employee)
        return Response(ShiftAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"shift-assignments/(?P<assignment_id>[0-9]+)")
    def delete_shift_assignment(self, request, employee_id=None, assignment_id=None):
        employee = self.get_object()
        row = ShiftAssignment.objects.filter(employee=employee, pk=assignment_id).first()
        if not row:
            return Response({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
