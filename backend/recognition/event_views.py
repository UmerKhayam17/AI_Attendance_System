from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from attendance.services.decision_engine import AttendanceDecisionEngine
from employees.models import Employee
from organizations.permissions import CanOperate, CanView
from recognition.models import RecognitionEvent
from recognition.serializers import RecognitionEventSerializer


class RecognitionEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RecognitionEventSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        return [CanOperate()]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            return RecognitionEvent.objects.none()
        qs = RecognitionEvent.objects.select_related("employee", "camera").filter(organization=org)
        kind = self.request.query_params.get("kind")
        if kind and kind != "all":
            qs = qs.filter(kind=kind)
        status_filter = self.request.query_params.get("status", "open")
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        camera_id = self.request.query_params.get("camera")
        if camera_id:
            qs = qs.filter(camera_id=camera_id)
        day = self.request.query_params.get("date")
        if day:
            parsed = parse_date(day)
            if parsed:
                qs = qs.filter(detected_at__date=parsed)
        return qs

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        event = self.get_object()
        event.status = RecognitionEvent.STATUS_DISMISSED
        event.save(update_fields=["status"])
        return Response(RecognitionEventSerializer(event, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        event = self.get_object()
        if event.kind not in (RecognitionEvent.KIND_UNKNOWN, RecognitionEvent.KIND_ANOMALY):
            return Response({"error": "Only unknown or anomaly events can be assigned"}, status=status.HTTP_400_BAD_REQUEST)
        employee_id = request.data.get("employee_id")
        employee = get_object_or_404(
            Employee,
            organization=request.organization,
            employee_id=employee_id,
            is_active=True,
        )
        camera = event.camera
        zone = camera.zone if camera else "mixed"
        decision = AttendanceDecisionEngine.process_recognition(
            employee=employee,
            confidence=event.confidence or 0.5,
            source=event.source or "cctv",
            zone=zone,
        )
        event.status = RecognitionEvent.STATUS_ASSIGNED
        event.employee = employee
        event.attendance_action = decision["action"]
        event.save(update_fields=["status", "employee", "attendance_action"])
        data = RecognitionEventSerializer(event, context={"request": request}).data
        data["attendance"] = {
            "action": decision["action"],
            "message": decision["message"],
            "status": decision["record"].status,
        }
        return Response(data)

    @action(detail=False, methods=["post"])
    def dismiss_all(self, request):
        qs = self.get_queryset().filter(status=RecognitionEvent.STATUS_OPEN)
        count = qs.count()
        qs.update(status=RecognitionEvent.STATUS_DISMISSED)
        return Response({"dismissed": count})
