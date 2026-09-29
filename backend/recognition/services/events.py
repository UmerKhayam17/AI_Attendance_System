from datetime import timedelta

import cv2
from django.core.files.base import ContentFile
from django.utils import timezone

from employees.models import Employee
from recognition.models import Camera, RecognitionEvent

UNKNOWN_COOLDOWN = timedelta(minutes=8)
SPOOF_COOLDOWN = timedelta(minutes=5)
REPEATED_UNKNOWN_THRESHOLD = 5


def _attach_image(event: RecognitionEvent, frame, bbox, camera_id: int | None):
    if frame is None:
        return
    img = frame.copy()
    if bbox is not None and len(bbox) == 4:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(img, (x1, y1), (x2, y2), (40, 80, 255), 2)
    h, w = img.shape[:2]
    if w > 960:
        scale = 960 / w
        img = cv2.resize(img, (960, int(h * scale)))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return
    stamp = timezone.localtime().strftime("%H%M%S")
    name = f"{event.kind}_cam{camera_id or 0}_{stamp}.jpg"
    event.image.save(name, ContentFile(buf.tobytes()), save=False)


def record_event(
    *,
    organization_id: int,
    kind: str,
    camera_id: int | None = None,
    camera_name: str = "",
    employee=None,
    confidence: float = 0.0,
    message: str = "",
    extra: dict | None = None,
    frame=None,
    bbox=None,
    track_id: int | None = None,
    source: str = "cctv",
    attendance_action: str = "",
    cooldown: timedelta | None = None,
    cooldown_keys: tuple[str, ...] = (),
    status: str = RecognitionEvent.STATUS_OPEN,
) -> RecognitionEvent | None:
    if cooldown is not None:
        since = timezone.now() - cooldown
        pending = RecognitionEvent.objects.filter(
            organization_id=organization_id,
            kind=kind,
            detected_at__gte=since,
        )
        if camera_id:
            pending = pending.filter(camera_id=camera_id)
        if track_id is not None:
            pending = pending.filter(track_id=track_id)
        for key in cooldown_keys:
            pending = pending.filter(extra__has_key=key)
        if pending.exists():
            return None

    camera = Camera.objects.filter(pk=camera_id).first() if camera_id else None
    event = RecognitionEvent(
        organization_id=organization_id,
        camera=camera,
        employee=employee,
        kind=kind,
        camera_name=camera_name or (camera.name if camera else ""),
        confidence=round(float(confidence or 0), 4),
        message=(message or "")[:250],
        extra=extra or {},
        track_id=track_id,
        source=source,
        attendance_action=attendance_action,
        status=status,
    )
    _attach_image(event, frame, bbox, camera_id)
    event.save()
    return event


def record_unknown(**kwargs) -> RecognitionEvent | None:
    kwargs.setdefault("cooldown", UNKNOWN_COOLDOWN)
    event = record_event(kind=RecognitionEvent.KIND_UNKNOWN, **kwargs)
    if event:
        _maybe_repeated_unknown(event)
    return event


def record_spoof(**kwargs) -> RecognitionEvent | None:
    kwargs.setdefault("cooldown", SPOOF_COOLDOWN)
    return record_event(kind=RecognitionEvent.KIND_SPOOF, **kwargs)


def _maybe_repeated_unknown(event: RecognitionEvent):
    today = timezone.localdate()
    count = RecognitionEvent.objects.filter(
        organization_id=event.organization_id,
        camera_id=event.camera_id,
        kind=RecognitionEvent.KIND_UNKNOWN,
        detected_at__date=today,
    ).count()
    if count < REPEATED_UNKNOWN_THRESHOLD:
        return
    already = RecognitionEvent.objects.filter(
        organization_id=event.organization_id,
        camera_id=event.camera_id,
        kind=RecognitionEvent.KIND_ANOMALY,
        detected_at__date=today,
        extra__code="repeated_unknown",
    ).exists()
    if already:
        return
    RecognitionEvent.objects.create(
        organization_id=event.organization_id,
        camera=event.camera,
        kind=RecognitionEvent.KIND_ANOMALY,
        camera_name=event.camera_name,
        message=f"Unknown person seen {count} times today on {event.camera_name or 'camera'}",
        extra={"code": "repeated_unknown", "count": count},
        source=event.source,
    )


def flag_wrong_branch(employee, camera: Camera | None, *, confidence: float, source: str):
    if employee is None or camera is None:
        return None
    emp_branch = getattr(employee, "branch_id", None)
    cam_branch = getattr(camera, "branch_id", None)
    if not emp_branch or not cam_branch or emp_branch == cam_branch:
        return None
    expected = getattr(getattr(employee, "branch", None), "name", "") or str(emp_branch)
    actual = getattr(getattr(camera, "branch", None), "name", "") or str(cam_branch)
    return record_event(
        organization_id=employee.organization_id,
        kind=RecognitionEvent.KIND_ANOMALY,
        camera_id=camera.id,
        camera_name=camera.name,
        employee=employee,
        confidence=confidence,
        message=f"{employee.first_name} expected at {expected}, seen at {actual}",
        extra={"code": "wrong_branch", "expected_branch": expected, "actual_branch": actual},
        source=source,
        cooldown=timedelta(hours=4),
    )


def flag_unusual_hours(employee, *, confidence: float, camera: Camera | None, source: str):
    if employee is None:
        return None
    from datetime import datetime, timedelta as td

    from organizations.localtime import local_now
    from organizations.shifts import schedule_for

    now = local_now(employee=employee)
    shift = schedule_for(employee=employee, on_date=now.date())
    start = getattr(shift, "start_time", None)
    if start is None:
        return None
    start_dt = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
    if now < start_dt - td(hours=3):
        return record_event(
            organization_id=employee.organization_id,
            kind=RecognitionEvent.KIND_ANOMALY,
            camera_id=camera.id if camera else None,
            camera_name=camera.name if camera else "",
            employee=employee,
            confidence=confidence,
            message=f"{employee.first_name} recognized {now.strftime('%H:%M')}, shift starts {start.strftime('%H:%M')}",
            extra={"code": "unusual_hours", "local_time": now.strftime("%H:%M"), "shift_start": start.strftime("%H:%M")},
            source=source,
            cooldown=timedelta(hours=6),
        )
    return None


def employee_for_id(organization_id: int, employee_id: str) -> Employee | None:
    if not employee_id:
        return None
    return Employee.objects.filter(
        organization_id=organization_id,
        employee_id=employee_id,
        is_active=True,
    ).select_related("branch").first()
