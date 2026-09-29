from datetime import timedelta

import cv2
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.utils import timezone

from employees.models import Employee
from recognition.models import Camera, MatchReview


def enqueue_match_review(
    *,
    organization_id: int,
    suggested_employee_id: str | None,
    camera_id: int | None,
    camera_name: str,
    frame,
    bbox,
    confidence: float,
    second_best: float | None,
    reason: str,
    track_id: int | None = None,
    source: str = "cctv",
) -> MatchReview | None:
    close_old_connections()
    since = timezone.now() - timedelta(minutes=10)
    pending = MatchReview.objects.filter(
        organization_id=organization_id,
        suggested_employee_id=suggested_employee_id or "",
        status=MatchReview.STATUS_PENDING,
        detected_at__gte=since,
    )
    if camera_id:
        pending = pending.filter(camera_id=camera_id)
    if pending.exists():
        return None

    employee = None
    if suggested_employee_id:
        employee = Employee.objects.filter(
            organization_id=organization_id,
            employee_id=suggested_employee_id,
            is_active=True,
        ).first()

    camera = Camera.objects.filter(pk=camera_id).first() if camera_id else None
    review = MatchReview(
        organization_id=organization_id,
        employee=employee,
        camera=camera,
        camera_name=camera_name or "",
        confidence=round(float(confidence), 4),
        second_best=None if second_best is None else round(float(second_best), 4),
        reason=reason,
        suggested_employee_id=suggested_employee_id or "",
        track_id=track_id,
        source=source,
    )

    if frame is not None:
        img = frame.copy()
        if bbox is not None and len(bbox) == 4:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 180, 255), 2)
        h, w = img.shape[:2]
        if w > 960:
            scale = 960 / w
            img = cv2.resize(img, (960, int(h * scale)))
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            stamp = timezone.localtime().strftime("%H%M%S")
            name = f"{suggested_employee_id or 'unknown'}_cam{camera_id or 0}_{stamp}.jpg"
            review.image.save(name, ContentFile(buf.tobytes()), save=False)

    review.save()
    return review
