from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from approvals.engine import approve as approval_approve
from approvals.engine import pending_for, reject as approval_reject, submit
from approvals.lock import assert_dates_unlocked
from approvals.models import ApprovalWorkflow
from attendance.leave_types import seed_leave_types
from attendance.models import (
    AttendanceCorrection,
    AttendanceRecord,
    Holiday,
    LeaveRequest,
    LeaveType,
    OvertimeRequest,
)
from attendance.serializers import (
    AttendanceCorrectionSerializer,
    AttendanceRecordSerializer,
    HolidaySerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
    ManualAttendanceSerializer,
    OvertimeRequestSerializer,
)
from attendance.services.decision_engine import AttendanceDecisionEngine
from attendance.services.leave_sync import sync_leave_records
from payroll.services.leave_policy import assert_leave_allowed
from attendance.services.school_webhook import notify_school
from employees.models import Employee
from organizations.localtime import local_date
from organizations.mixins import OrganizationScopedMixin
from organizations.permissions import CanOperate, CanView, HasOrganization, IsOwnerOrAdmin, IsStaffOrPortal
from organizations.query import parse_branch_id


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [CanView]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return AttendanceRecord.objects.none()
        qs = AttendanceRecord.objects.select_related("employee", "employee__branch").filter(
            employee__organization=org
        ).order_by("-date")
        employee_id = self.request.query_params.get("employee_id")
        date = self.request.query_params.get("date")
        status_filter = self.request.query_params.get("status")
        branch_id = parse_branch_id(self.request)

        if employee_id:
            qs = qs.filter(employee__employee_id=employee_id)
        if date:
            qs = qs.filter(date=date)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if branch_id:
            qs = qs.filter(employee__branch_id=branch_id)
        return qs


class ManualAttendanceView(APIView):
    permission_classes = [CanOperate]

    def post(self, request):
        serializer = ManualAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = Employee.objects.select_related("shift", "branch", "organization").filter(
            organization=request.organization,
            employee_id=serializer.validated_data["employee_id"],
            is_active=True,
        ).first()
        if not employee:
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        today = local_date(employee=employee, organization=request.organization, now=now)
        try:
            assert_dates_unlocked(request.organization, today, today)
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record, _ = AttendanceRecord.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={"source": AttendanceRecord.SOURCE_MANUAL},
        )

        action_type = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")

        if action_type == "check_in":
            if record.check_in:
                return Response(
                    {"error": "Already checked in today"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            record.check_in = now
            record.status = AttendanceDecisionEngine.determine_status(
                now, employee=employee, organization=request.organization
            )
            record.source = AttendanceRecord.SOURCE_MANUAL
            if notes:
                record.notes = notes
            record.save()
            notify_school(record, "check_in")
            if record.status == AttendanceRecord.STATUS_LATE:
                from attendance.services.notifier import notify_event_async

                notify_event_async(employee.id, "late", record.id)

        elif action_type == "check_out":
            if not record.check_in:
                return Response(
                    {"error": "Must check in first"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if record.check_out:
                return Response(
                    {"error": "Already checked out today"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            record.check_out = now
            if notes:
                record.notes = notes
            from attendance.services.shift_rules import apply_checkout_rules

            apply_checkout_rules(record, employee=employee, now=now)
            record.save()
            notify_school(record, "check_out")
            from attendance.services.overtime import maybe_suggest_overtime

            maybe_suggest_overtime(record, employee)

        return Response(AttendanceRecordSerializer(record).data)


class HolidayViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        branch_id = parse_branch_id(self.request)
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        return qs

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        if self.action in ("approve", "reject"):
            return [HasOrganization(), IsStaffOrPortal()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return LeaveRequest.objects.none()
        qs = LeaveRequest.objects.select_related("employee", "decided_by").filter(
            employee__organization=org
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        leave = serializer.save()
        submit(
            organization=self.request.organization,
            kind=ApprovalWorkflow.KIND_LEAVE,
            target_id=leave.pk,
            employee=leave.employee,
            user=self.request.user,
        )

    def perform_update(self, serializer):
        leave = serializer.save()
        if leave.status == LeaveRequest.STATUS_APPROVED:
            assert_leave_allowed(leave)
            sync_leave_records(leave)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        leave = self.get_object()
        row = pending_for(request.organization, ApprovalWorkflow.KIND_LEAVE, leave.pk)
        if row is None:
            row = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_LEAVE,
                target_id=leave.pk,
                employee=leave.employee,
                user=request.user,
            )
        try:
            approval_approve(row, request.user, (request.data or {}).get("comment") or "")
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        leave.refresh_from_db()
        return Response(LeaveRequestSerializer(leave, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        leave = self.get_object()
        row = pending_for(request.organization, ApprovalWorkflow.KIND_LEAVE, leave.pk)
        if row is None:
            row = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_LEAVE,
                target_id=leave.pk,
                employee=leave.employee,
                user=request.user,
            )
        try:
            approval_reject(row, request.user, (request.data or {}).get("comment") or "")
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        leave.refresh_from_db()
        return Response(LeaveRequestSerializer(leave, context={"request": request}).data)


class LeaveTypeListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [IsStaffOrPortal()]

    def get(self, request):
        seed_leave_types(request.organization)
        rows = LeaveType.objects.filter(organization=request.organization)
        return Response(LeaveTypeSerializer(rows, many=True).data)

    def post(self, request):
        seed_leave_types(request.organization)
        serializer = LeaveTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=request.organization)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeaveTypeDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        row = get_object_or_404(LeaveType, organization=request.organization, pk=pk)
        serializer = LeaveTypeSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        row = get_object_or_404(LeaveType, organization=request.organization, pk=pk)
        row.is_active = False
        row.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AttendanceCorrectionViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceCorrectionSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        if self.action in ("approve", "reject"):
            return [HasOrganization(), IsStaffOrPortal()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return AttendanceCorrection.objects.none()
        return AttendanceCorrection.objects.select_related("employee", "decided_by").filter(
            employee__organization=org
        )

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        day = serializer.validated_data["date"]
        record = AttendanceRecord.objects.filter(employee=employee, date=day).first()
        row = serializer.save(
            original_check_in=record.check_in if record else None,
            original_check_out=record.check_out if record else None,
            original_status=record.status if record else "",
        )
        submit(
            organization=self.request.organization,
            kind=ApprovalWorkflow.KIND_CORRECTION,
            target_id=row.pk,
            employee=employee,
            user=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        row = self.get_object()
        pending = pending_for(request.organization, ApprovalWorkflow.KIND_CORRECTION, row.pk)
        if pending is None:
            pending = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_CORRECTION,
                target_id=row.pk,
                employee=row.employee,
                user=request.user,
            )
        try:
            approval_approve(pending, request.user, (request.data or {}).get("comment") or "")
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=400)
        row.refresh_from_db()
        return Response(AttendanceCorrectionSerializer(row, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        row = self.get_object()
        pending = pending_for(request.organization, ApprovalWorkflow.KIND_CORRECTION, row.pk)
        if pending is None:
            pending = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_CORRECTION,
                target_id=row.pk,
                employee=row.employee,
                user=request.user,
            )
        approval_reject(pending, request.user, (request.data or {}).get("comment") or "")
        row.refresh_from_db()
        return Response(AttendanceCorrectionSerializer(row, context={"request": request}).data)


class OvertimeRequestViewSet(viewsets.ModelViewSet):
    serializer_class = OvertimeRequestSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        if self.action in ("approve", "reject"):
            return [HasOrganization(), IsStaffOrPortal()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return OvertimeRequest.objects.none()
        return OvertimeRequest.objects.select_related("employee", "decided_by").filter(
            employee__organization=org
        )

    def perform_create(self, serializer):
        row = serializer.save(source=OvertimeRequest.SOURCE_MANUAL)
        submit(
            organization=self.request.organization,
            kind=ApprovalWorkflow.KIND_OVERTIME,
            target_id=row.pk,
            employee=row.employee,
            user=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        row = self.get_object()
        pending = pending_for(request.organization, ApprovalWorkflow.KIND_OVERTIME, row.pk)
        if pending is None:
            pending = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_OVERTIME,
                target_id=row.pk,
                employee=row.employee,
                user=request.user,
            )
        try:
            approval_approve(pending, request.user, (request.data or {}).get("comment") or "")
        except ValidationError as exc:
            return Response(exc.detail if hasattr(exc, "detail") else {"error": str(exc)}, status=400)
        row.refresh_from_db()
        return Response(OvertimeRequestSerializer(row, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        row = self.get_object()
        pending = pending_for(request.organization, ApprovalWorkflow.KIND_OVERTIME, row.pk)
        if pending is None:
            pending = submit(
                organization=request.organization,
                kind=ApprovalWorkflow.KIND_OVERTIME,
                target_id=row.pk,
                employee=row.employee,
                user=request.user,
            )
        approval_reject(pending, request.user, (request.data or {}).get("comment") or "")
        row.refresh_from_db()
        return Response(OvertimeRequestSerializer(row, context={"request": request}).data)
