from pathlib import Path

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.services.decision_engine import AttendanceDecisionEngine
from employees.models import Employee
from organizations.permissions import CanOperate, CanView
from recognition.models import FaceEnrollment
from recognition.serializers import (
    CaptureImageSerializer,
    FaceEnrollmentDetailSerializer,
    IdentifySerializer,
)
from recognition.services.face_engine import get_face_engine
from recognition.services.gallery_index import get_gallery_index
from recognition.services.match_confirm import CONFIRM_WEBCAM, get_match_confirmer
from recognition.services.review_queue import enqueue_match_review
from recognition.services.training import MIN_ENROLLMENT_IMAGES, TrainingError, train_enrollment


def _enrollment_for(organization, employee_id):
    return get_object_or_404(
        FaceEnrollment.objects.select_related("employee"),
        employee__employee_id=employee_id,
        employee__organization=organization,
    )


class EnrollmentStatusView(APIView):
    permission_classes = [CanOperate]

    def get(self, request, employee_id):
        enrollment = _enrollment_for(request.organization, employee_id)
        return Response(FaceEnrollmentDetailSerializer(enrollment).data)


class CaptureFaceView(APIView):
    permission_classes = [CanOperate]

    def post(self, request, employee_id):
        serializer = CaptureImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = get_object_or_404(
            Employee,
            employee_id=employee_id,
            is_active=True,
            organization=request.organization,
        )
        enrollment = get_object_or_404(FaceEnrollment, employee=employee)

        engine = get_face_engine()
        try:
            image = engine.decode_base64(serializer.validated_data["image"])
        except (ValueError, Exception):
            return Response(
                {"error": "Invalid image data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quality = engine.check_quality(image)
        save_image = quality.pop("image", None)
        if save_image is None:
            save_image = engine.resize_max(image, 640)
        if not quality["passed"]:
            return Response({"accepted": False, "quality": quality})

        folder = Path(settings.MEDIA_ROOT) / enrollment.dataset_folder
        index = enrollment.total_images + 1
        engine.save_dataset_image(save_image, folder, index)

        enrollment.total_images = index
        enrollment.is_enrolled = enrollment.total_images >= MIN_ENROLLMENT_IMAGES
        enrollment.is_trained = False
        enrollment.embedding = None
        enrollment.embeddings = None
        enrollment.save(update_fields=[
            "total_images", "is_enrolled", "is_trained", "embedding", "embeddings", "updated_at"
        ])

        if index == 1:
            profile_rel = engine.save_profile_image(
                save_image, employee.employee_id, org_id=employee.organization_id
            )
            enrollment.profile_image = profile_rel
            enrollment.save(update_fields=["profile_image", "updated_at"])

        return Response({
            "accepted": True,
            "quality": quality,
            "total_images": enrollment.total_images,
            "images_required": MIN_ENROLLMENT_IMAGES,
            "is_enrolled": enrollment.is_enrolled,
        })


class TrainEmbeddingsView(APIView):
    permission_classes = [CanOperate]

    def post(self, request, employee_id):
        enrollment = _enrollment_for(request.organization, employee_id)

        try:
            result = train_enrollment(enrollment)
        except TrainingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "trained": True,
            "embedding_dim": result["embedding_dim"],
            "images_used": result["images_used"],
            "embeddings_stored": result["embeddings_stored"],
            "model_version": result["model_version"],
            "enrollment": FaceEnrollmentDetailSerializer(result["enrollment"]).data,
        })


class IdentifyFaceView(APIView):
    permission_classes = [CanOperate]

    def post(self, request):
        serializer = IdentifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        engine = get_face_engine()
        try:
            image = engine.decode_base64(serializer.validated_data["image"])
        except (ValueError, Exception):
            return Response(
                {"error": "Invalid image data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = serializer.validated_data.get("source", "cctv")
        gallery = get_gallery_index(request.organization.id)
        liveness_mode = "webcam" if source in ("webcam", "mobile") else "cctv"
        result = engine.identify_from_image(
            image,
            gallery,
            check_liveness=True,
            liveness_mode=liveness_mode,
        )

        response = dict(result)
        if result.get("liveness") and not result["liveness"].get("passed") and not result["liveness"].get("skipped"):
            from recognition.services.events import record_spoof

            record_spoof(
                organization_id=request.organization.id,
                camera_name="Mobile camera" if source == "mobile" else "Webcam",
                message=result.get("message") or "Spoof attempt",
                extra={"liveness": result["liveness"].get("score")},
                frame=image,
                source=source,
            )
            return Response(response)

        if result.get("needs_review") and not result.get("matched"):
            enqueue_match_review(
                organization_id=request.organization.id,
                suggested_employee_id=result.get("candidate_id"),
                camera_id=None,
                camera_name="Mobile camera" if source == "mobile" else "Webcam",
                frame=image,
                bbox=None,
                confidence=result.get("confidence") or 0.0,
                second_best=None,
                reason="ambiguous" if result.get("ambiguous") else "low_confidence",
                source=source if source in ("webcam", "mobile", "cctv") else "webcam",
            )
            response["attendance"] = {
                "action": "review",
                "message": "Queued for human review",
                "date": None,
                "check_in": None,
                "check_out": None,
                "status": "",
            }
            return Response(response)

        if not result.get("matched") and not result.get("needs_review"):
            from recognition.services.events import record_unknown

            record_unknown(
                organization_id=request.organization.id,
                camera_name="Mobile camera" if source == "mobile" else "Webcam",
                confidence=result.get("confidence") or 0,
                message=result.get("message") or "Unknown face",
                extra={"candidate_id": result.get("candidate_id")},
                frame=image,
                source=source if source in ("webcam", "mobile", "cctv") else "webcam",
            )

        if (
            result["matched"]
            and serializer.validated_data.get("mark_attendance")
        ):
            employee = get_object_or_404(
                Employee,
                employee_id=result["employee_id"],
                is_active=True,
                organization=request.organization,
            )
            if not FaceEnrollment.objects.filter(
                employee=employee, is_trained=True
            ).exists():
                return Response(
                    {"error": "Employee face not trained"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if source == "mobile":
                from organizations.geofence import assert_inside_geofence

                lat = serializer.validated_data.get("latitude")
                lng = serializer.validated_data.get("longitude")
                geo = assert_inside_geofence(
                    employee.branch or request.organization.default_branch(),
                    lat,
                    lng,
                )
                response["geofence"] = geo
            else:
                confirm = get_match_confirmer().observe(
                    organization_id=request.organization.id,
                    source_key=f"webcam:{request.organization.id}",
                    employee_id=employee.employee_id,
                    required=CONFIRM_WEBCAM,
                )
                if not confirm.confirmed:
                    response["attendance"] = {
                        "action": "pending",
                        "message": confirm.message,
                        "date": None,
                        "check_in": None,
                        "check_out": None,
                        "status": "",
                        "hits": confirm.hits,
                        "required": confirm.required,
                    }
                    return Response(response)

            decision = AttendanceDecisionEngine.process_recognition(
                employee=employee,
                confidence=result["confidence"],
                source=source if source in ("cctv", "webcam", "mobile") else "webcam",
                zone="mixed",
                latitude=serializer.validated_data.get("latitude"),
                longitude=serializer.validated_data.get("longitude"),
            )
            record = decision["record"]
            response["attendance"] = {
                "action": decision["action"],
                "message": decision["message"],
                "date": str(record.date),
                "check_in": record.check_in,
                "check_out": record.check_out,
                "status": record.status,
            }

        return Response(response)


class GalleryStatsView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        org = request.organization
        qs = FaceEnrollment.objects.filter(employee__organization=org)
        total = qs.count()
        enrolled = qs.filter(is_enrolled=True).count()
        trained = qs.filter(is_trained=True).count()
        return Response({
            "total_employees_with_enrollment": total,
            "enrolled": enrolled,
            "trained": trained,
            "ready_for_recognition": trained,
        })
