from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from attendance.services.decision_engine import AttendanceDecisionEngine
from employees.models import Employee
from organizations.permissions import CanOperate, CanView
from recognition.models import MatchReview
from recognition.serializers import MatchReviewSerializer


class MatchReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MatchReviewSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        return [CanOperate()]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return MatchReview.objects.none()
        qs = MatchReview.objects.select_related("employee", "camera", "reviewed_by").filter(
            organization=org
        )
        status_filter = self.request.query_params.get("status", "pending")
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        review = self.get_object()
        if review.status != MatchReview.STATUS_PENDING:
            return Response({"error": "This review is already decided"}, status=status.HTTP_400_BAD_REQUEST)

        employee_id = request.data.get("employee_id") or review.suggested_employee_id
        employee = get_object_or_404(
            Employee,
            organization=request.organization,
            employee_id=employee_id,
            is_active=True,
        )
        camera = review.camera
        zone = camera.zone if camera else "mixed"
        decision = AttendanceDecisionEngine.process_recognition(
            employee=employee,
            confidence=review.confidence,
            source=review.source or "cctv",
            zone=zone,
        )
        review.status = MatchReview.STATUS_CONFIRMED
        review.employee = employee
        review.suggested_employee_id = employee.employee_id
        review.reviewed_by = request.user
        review.reviewed_at = timezone.now()
        review.attendance_action = decision["action"]
        review.save()
        data = MatchReviewSerializer(review, context={"request": request}).data
        data["attendance"] = {
            "action": decision["action"],
            "message": decision["message"],
            "status": decision["record"].status,
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        review = self.get_object()
        if review.status != MatchReview.STATUS_PENDING:
            return Response({"error": "This review is already decided"}, status=status.HTTP_400_BAD_REQUEST)
        review.status = MatchReview.STATUS_REJECTED
        review.reviewed_by = request.user
        review.reviewed_at = timezone.now()
        review.notes = request.data.get("notes") or review.notes
        review.save()
        return Response(MatchReviewSerializer(review, context={"request": request}).data)
