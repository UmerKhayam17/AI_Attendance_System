from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from exits.models import ExitCase, ExitChecklistTemplate, ExitClearanceItem, ExitPolicy
from exits.serializers import (
    ExitCaseSerializer,
    ExitCaseWriteSerializer,
    ExitChecklistTemplateSerializer,
    ExitClearanceItemSerializer,
    ExitPolicySerializer,
)
from exits.services import complete_exit, init_exit_module, initiate_exit, notice_days_for, suggested_last_working_day
from organizations.permissions import CanView, IsOwnerOrAdmin


class ExitPolicyView(APIView):
    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        policy = init_exit_module(request.organization)
        return Response(ExitPolicySerializer(policy).data)

    def patch(self, request):
        policy = init_exit_module(request.organization)
        serializer = ExitPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ExitChecklistTemplateListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        init_exit_module(request.organization)
        rows = ExitChecklistTemplate.objects.filter(organization=request.organization)
        return Response(ExitChecklistTemplateSerializer(rows, many=True).data)

    def post(self, request):
        init_exit_module(request.organization)
        serializer = ExitChecklistTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=request.organization)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExitChecklistTemplateDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def patch(self, request, pk):
        row = get_object_or_404(ExitChecklistTemplate, organization=request.organization, pk=pk)
        serializer = ExitChecklistTemplateSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        row = get_object_or_404(ExitChecklistTemplate, organization=request.organization, pk=pk)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExitCaseListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        qs = ExitCase.objects.filter(organization=request.organization).select_related(
            "employee", "employee__department", "initiated_by"
        ).prefetch_related("checklist_items")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ExitCaseSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ExitCaseWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        case = initiate_exit(
            organization=request.organization,
            employee=serializer.validated_data["employee"],
            user=request.user,
            data=serializer.validated_data,
        )
        case = ExitCase.objects.prefetch_related("checklist_items").select_related(
            "employee", "employee__department", "initiated_by"
        ).get(pk=case.pk)
        return Response(ExitCaseSerializer(case).data, status=status.HTTP_201_CREATED)


def _case(request, pk):
    return get_object_or_404(
        ExitCase.objects.select_related("employee", "employee__department", "initiated_by").prefetch_related(
            "checklist_items"
        ),
        organization=request.organization,
        pk=pk,
    )


class ExitCaseDetailView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request, pk):
        return Response(ExitCaseSerializer(_case(request, pk)).data)

    def patch(self, request, pk):
        case = _case(request, pk)
        if case.status in (ExitCase.STATUS_COMPLETED, ExitCase.STATUS_CANCELLED):
            return Response({"error": "This exit can no longer be edited"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ExitCaseSerializer(case, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ExitCaseSerializer(_case(request, pk)).data)


class ExitCaseCompleteView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request, pk):
        case = complete_exit(_case(request, pk), request.user)
        return Response(ExitCaseSerializer(_case(request, pk)).data)


class ExitCaseCancelView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request, pk):
        case = _case(request, pk)
        if case.status == ExitCase.STATUS_COMPLETED:
            return Response({"error": "Completed exits cannot be cancelled"}, status=status.HTTP_400_BAD_REQUEST)
        case.status = ExitCase.STATUS_CANCELLED
        case.save(update_fields=["status", "updated_at"])
        return Response(ExitCaseSerializer(_case(request, pk)).data)


class ExitClearanceToggleView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request, pk, item_id):
        case = _case(request, pk)
        if case.status in (ExitCase.STATUS_COMPLETED, ExitCase.STATUS_CANCELLED):
            return Response({"error": "This exit can no longer be updated"}, status=status.HTTP_400_BAD_REQUEST)
        item = get_object_or_404(ExitClearanceItem, case=case, pk=item_id)
        item.is_cleared = not item.is_cleared
        item.notes = request.data.get("notes", item.notes)
        if item.is_cleared:
            item.cleared_by = request.user
            item.cleared_at = timezone.now()
        else:
            item.cleared_by = None
            item.cleared_at = None
        item.save()
        if case.status == ExitCase.STATUS_INITIATED:
            case.status = ExitCase.STATUS_IN_PROGRESS
            case.save(update_fields=["status", "updated_at"])
        return Response(ExitClearanceItemSerializer(item).data)


class ExitSuggestView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        from employees.models import Employee

        employee_id = request.query_params.get("employee_id")
        employee = get_object_or_404(Employee, organization=request.organization, employee_id=employee_id)
        policy = init_exit_module(request.organization)
        resignation = date_from_query(request.query_params.get("resignation_date"))
        lwd = suggested_last_working_day(policy, employee, resignation)
        notice = notice_days_for(policy, employee, resignation)
        return Response({
            "notice_period_days": notice,
            "last_working_day": str(lwd),
            "in_probation": notice == policy.probation_notice_days and policy.probation_notice_days != policy.notice_period_days,
        })


def date_from_query(value):
    from datetime import date

    if value:
        return date.fromisoformat(value)
    return date.today()
