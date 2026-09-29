from rest_framework.exceptions import ValidationError

from attendance.models import AttendanceRecord
from attendance.services.decision_engine import AttendanceDecisionEngine
from organizations.geofence import assert_inside_geofence, geofence_status
from recognition.models import FaceEnrollment


def _coord(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def punch_context(employee, organization) -> dict:
    branch = getattr(employee, "branch", None) or organization.default_branch()
    trained = FaceEnrollment.objects.filter(employee=employee, is_trained=True).exists()
    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.display_name if hasattr(employee, "display_name") else f"{employee.first_name} {employee.last_name}".strip(),
        "trained": trained,
        "geofence": geofence_status(branch),
    }


def selfie_punch(*, organization, employee, image_b64: str, latitude, longitude) -> dict:
    if employee is None or not employee.is_active:
        raise ValidationError({"employee": "No active employee profile is linked to this login"})
    if not FaceEnrollment.objects.filter(employee=employee, is_trained=True).exists():
        raise ValidationError({"face": "Your face is not enrolled yet. Ask HR to enroll you first."})

    branch = employee.branch or organization.default_branch()
    geo = assert_inside_geofence(branch, _coord(latitude), _coord(longitude))

    from recognition.services.face_engine import get_face_engine
    from recognition.services.gallery_index import get_gallery_index

    engine = get_face_engine()
    try:
        image = engine.decode_base64(image_b64)
    except (ValueError, Exception):
        raise ValidationError({"image": "Invalid camera image"}) from None

    gallery = get_gallery_index(organization.id)
    result = engine.identify_from_image(
        image,
        gallery,
        check_liveness=True,
        liveness_mode="webcam",
    )
    liveness = result.get("liveness") or {}
    if liveness and not liveness.get("passed") and not liveness.get("skipped"):
        raise ValidationError({"face": liveness.get("message") or "Liveness check failed. Use a live selfie."})
    if not result.get("matched"):
        raise ValidationError({"face": result.get("message") or "Face not recognized"})
    if result.get("employee_id") != employee.employee_id:
        raise ValidationError({"face": "This face does not match your profile"})

    decision = AttendanceDecisionEngine.process_recognition(
        employee=employee,
        confidence=result.get("confidence") or 0,
        source=AttendanceRecord.SOURCE_MOBILE,
        latitude=_coord(latitude),
        longitude=_coord(longitude),
    )
    record = decision["record"]
    return {
        "matched": True,
        "employee_id": employee.employee_id,
        "confidence": result.get("confidence") or 0,
        "liveness": liveness,
        "geofence": geo,
        "attendance": {
            "action": decision["action"],
            "message": decision["message"],
            "date": str(record.date),
            "check_in": record.check_in,
            "check_out": record.check_out,
            "status": record.status,
            "source": record.source,
        },
    }
