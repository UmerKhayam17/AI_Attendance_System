from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.limits import camera_quota, ensure_camera_slot
from organizations.mixins import OrganizationScopedMixin
from organizations.permissions import CanOperate, CanView, IsOwnerOrAdmin
from organizations.query import parse_branch_id
from recognition.models import Camera, DetectionSnapshot
from recognition.serializers import CameraSerializer, DetectionSnapshotSerializer
from recognition.services.cctv_worker import get_cctv_manager
from recognition.services.dwell import overview_for
from recognition.services.snapshot_saver import snapshot_to_dict


def _start_payload(camera):
    return {
        "id": camera.id,
        "name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "organization_id": camera.organization_id,
        "zone": camera.zone,
    }


class CameraViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ("list", "retrieve", "snapshot", "status", "start", "stop"):
            if self.action in ("start", "stop"):
                return [CanOperate()]
            return [CanOperate()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsOwnerOrAdmin()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        branch_id = parse_branch_id(self.request)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["cctv_manager"] = get_cctv_manager()
        return ctx

    def perform_create(self, serializer):
        ensure_camera_slot(self.request.organization)
        org = self.request.organization
        branch = serializer.validated_data.get("branch") or org.default_branch()
        serializer.save(organization=org, branch=branch)

    def perform_update(self, serializer):
        serializer.save(organization=self.request.organization)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        camera = self.get_object()
        if not camera.is_active:
            return Response(
                {"error": "Camera is inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        quota = camera_quota(request.organization)
        if quota <= 0:
            return Response(
                {"error": "Your plan does not include CCTV cameras"},
                status=status.HTTP_403_FORBIDDEN,
            )
        manager = get_cctv_manager()
        running = [
            s for s in manager.list_status()
            if s["running"] and s.get("organization_id") == request.organization.id
        ]
        already = any(s["camera_id"] == camera.id for s in running)
        if not already and len(running) >= quota:
            return Response(
                {"error": f"Camera start limit reached ({quota}) for your plan"},
                status=status.HTTP_403_FORBIDDEN,
            )
        runtime = manager.start_camera(
            camera.id,
            camera.name,
            camera.rtsp_url,
            organization_id=camera.organization_id,
            zone=camera.zone,
        )
        return Response({
            "camera": CameraSerializer(camera, context=self.get_serializer_context()).data,
            "runtime": runtime,
        })

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        camera = self.get_object()
        manager = get_cctv_manager()
        runtime = manager.stop_camera(camera.id)
        return Response({"runtime": runtime})

    @action(detail=True, methods=["get"])
    def snapshot(self, request, pk=None):
        camera = self.get_object()
        jpeg = get_cctv_manager().get_snapshot_jpeg(camera.id)
        if not jpeg:
            return Response(
                {"error": "No snapshot available. Start the camera first."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return HttpResponse(jpeg, content_type="image/jpeg")

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        camera = self.get_object()
        runtime = get_cctv_manager().get_status(camera.id)
        return Response({
            "camera_id": camera.id,
            "name": camera.name,
            "runtime": runtime,
        })


class CCTVControlView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [CanOperate()]
        return [CanOperate()]

    def get(self, request):
        manager = get_cctv_manager()
        cameras = Camera.objects.filter(
            is_active=True,
            organization=request.organization,
        )
        serializer = CameraSerializer(
            cameras,
            many=True,
            context={"cctv_manager": manager, "request": request},
        )
        recent = (
            DetectionSnapshot.objects.select_related("employee", "camera")
            .filter(employee__organization=request.organization)
            .order_by("-detected_at")[:24]
        )
        events = [
            e for e in manager.get_events(limit=80)
            if e.get("organization_id") == request.organization.id
            or e.get("camera_id") in {c.id for c in cameras}
        ]
        running_count = sum(
            1
            for s in manager.list_status()
            if s["running"] and s.get("organization_id") == request.organization.id
        )
        return Response({
            "cameras": serializer.data,
            "events": events[:40],
            "snapshots": [snapshot_to_dict(s) for s in recent],
            "running_count": running_count,
            "camera_quota": camera_quota(request.organization),
            "dwell": overview_for(request.organization),
        })

    def post(self, request):
        action_name = request.data.get("action", "start_all")
        manager = get_cctv_manager()
        quota = camera_quota(request.organization)
        cameras_qs = Camera.objects.filter(
            is_active=True,
            organization=request.organization,
        ).order_by("sort_order", "id")

        if action_name == "start_all":
            if quota <= 0:
                return Response(
                    {"error": "Your plan does not include CCTV cameras"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            cameras = [_start_payload(c) for c in cameras_qs[:quota]]
            statuses = manager.start_all(cameras)
            return Response({"action": "start_all", "statuses": statuses})

        if action_name == "stop_all":
            statuses = []
            for camera in cameras_qs:
                runtime = manager.stop_camera(camera.id)
                if runtime:
                    statuses.append(runtime)
            return Response({"action": "stop_all", "statuses": statuses})

        return Response(
            {"error": "Unknown action. Use start_all or stop_all."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CCTVEventsView(APIView):
    permission_classes = [CanOperate]

    def get(self, request):
        camera_id = request.query_params.get("camera_id")
        manager = get_cctv_manager()
        org_camera_ids = set(
            Camera.objects.filter(organization=request.organization).values_list("id", flat=True)
        )
        if camera_id:
            cid = int(camera_id)
            if cid not in org_camera_ids:
                return Response({"events": []})
            events = manager.get_events(camera_id=cid, limit=50)
        else:
            events = [
                e for e in manager.get_events(limit=80)
                if e.get("camera_id") in org_camera_ids
            ][:50]
        return Response({"events": events})


class DetectionSnapshotListView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        qs = DetectionSnapshot.objects.select_related("employee", "camera").filter(
            employee__organization=request.organization
        ).order_by("-detected_at")
        camera_id = request.query_params.get("camera_id")
        employee_id = request.query_params.get("employee_id")
        if camera_id:
            qs = qs.filter(camera_id=camera_id)
        if employee_id:
            qs = qs.filter(employee__employee_id=employee_id)
        limit = min(int(request.query_params.get("limit", 40)), 100)
        serializer = DetectionSnapshotSerializer(qs[:limit], many=True)
        return Response({"snapshots": serializer.data})
