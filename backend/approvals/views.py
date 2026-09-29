from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from approvals.bootstrap import seed_workflows
from approvals.engine import approve, inbox_for, reject
from approvals.models import ApprovalRequest, ApprovalWorkflow, AuditEvent, InAppNotification
from approvals.serializers import (
    ApprovalRequestSerializer,
    ApprovalWorkflowSerializer,
    AuditEventSerializer,
    InAppNotificationSerializer,
)
from organizations.permissions import CanView, HasOrganization, IsOwnerOrAdmin, IsStaffOrPortal


class WorkflowListView(APIView):
    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        seed_workflows(request.organization)
        rows = ApprovalWorkflow.objects.filter(organization=request.organization).prefetch_related("steps")
        return Response(ApprovalWorkflowSerializer(rows, many=True).data)


class WorkflowDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        seed_workflows(request.organization)
        row = get_object_or_404(ApprovalWorkflow, organization=request.organization, pk=pk)
        serializer = ApprovalWorkflowSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ApprovalWorkflowSerializer(row).data)


class InboxView(APIView):
    permission_classes = [HasOrganization, IsStaffOrPortal]

    def get(self, request):
        rows = inbox_for(request.user, request.organization)
        return Response(ApprovalRequestSerializer(rows, many=True, context={"request": request}).data)


class ApprovalDecideView(APIView):
    permission_classes = [HasOrganization, IsStaffOrPortal]

    def post(self, request, pk, action):
        row = get_object_or_404(
            ApprovalRequest.objects.select_related("current_step", "employee", "employee__manager", "employee__user"),
            organization=request.organization,
            pk=pk,
        )
        comment = (request.data or {}).get("comment") or ""
        try:
            if action == "approve":
                row = approve(row, request.user, comment)
            else:
                row = reject(row, request.user, comment)
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ApprovalRequestSerializer(row, context={"request": request}).data)


class NotificationListView(APIView):
    permission_classes = [HasOrganization]

    def get(self, request):
        qs = InAppNotification.objects.filter(organization=request.organization, user=request.user)
        unread = request.query_params.get("unread")
        if unread in ("1", "true"):
            qs = qs.filter(read_at__isnull=True)
        return Response(InAppNotificationSerializer(qs[:80], many=True).data)


class NotificationReadView(APIView):
    permission_classes = [HasOrganization]

    def post(self, request, pk=None):
        qs = InAppNotification.objects.filter(organization=request.organization, user=request.user, read_at__isnull=True)
        if pk:
            qs = qs.filter(pk=pk)
        qs.update(read_at=timezone.now())
        return Response({"ok": True})


class AuditListView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        qs = AuditEvent.objects.filter(organization=request.organization)[:200]
        return Response(AuditEventSerializer(qs, many=True).data)
