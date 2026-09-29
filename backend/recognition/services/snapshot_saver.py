import cv2
import numpy as np
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from recognition.models import Camera, DetectionSnapshot


def _annotate_frame(
    frame: np.ndarray,
    camera_id: int,
    camera_name: str,
    employee_id: str,
    confidence: float,
    bbox=None,
) -> np.ndarray:
    img = frame.copy()
    h, w = img.shape[:2]

    # Keep a readable preview size for storage
    max_w = 960
    if w > max_w:
        scale = max_w / w
        img = cv2.resize(img, (max_w, int(h * scale)))
        if bbox is not None:
            bbox = [int(v * scale) for v in bbox]

    if bbox is not None and len(bbox) == 4:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 200, 80), 2)

    stamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Camera #{camera_id}  {camera_name}",
        f"{employee_id}  {confidence * 100:.0f}%",
        stamp,
    ]

    y = 28
    for line in lines:
        cv2.putText(
            img,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            img,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 28

    return img


def save_detection_snapshot(
    *,
    employee,
    camera_id: int,
    camera_name: str,
    frame: np.ndarray,
    confidence: float,
    attendance_action: str = "",
    bbox=None,
) -> DetectionSnapshot | None:
    """
    Save an annotated JPEG when an employee is recognized on CCTV.
    """
    try:
        annotated = _annotate_frame(
            frame,
            camera_id=camera_id,
            camera_name=camera_name,
            employee_id=employee.employee_id,
            confidence=confidence,
            bbox=bbox,
        )
        ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None

        camera = Camera.objects.filter(id=camera_id).first()
        stamp = timezone.localtime().strftime("%H%M%S")
        filename = f"{employee.employee_id}_cam{camera_id}_{stamp}.jpg"

        snapshot = DetectionSnapshot(
            employee=employee,
            camera=camera,
            camera_name=camera_name or f"Camera {camera_id}",
            confidence=round(confidence, 4),
            attendance_action=attendance_action or "",
        )
        snapshot.image.save(filename, ContentFile(buf.tobytes()), save=True)
        return snapshot
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to save detection snapshot")
        return None


def snapshot_to_dict(snapshot: DetectionSnapshot) -> dict:
    image_url = ""
    if snapshot.image:
        try:
            rel = Path(snapshot.image.name).as_posix()
            image_url = f"{settings.MEDIA_URL}{rel}"
        except Exception:
            image_url = snapshot.image.url

    return {
        "id": snapshot.id,
        "employee_id": snapshot.employee.employee_id,
        "employee_name": f"{snapshot.employee.first_name} {snapshot.employee.last_name}".strip(),
        "camera_id": snapshot.camera_id,
        "camera_name": snapshot.camera_name,
        "camera_label": f"Camera #{snapshot.camera_id or '?'} · {snapshot.camera_name}",
        "image_url": image_url,
        "confidence": snapshot.confidence,
        "attendance_action": snapshot.attendance_action,
        "detected_at": snapshot.detected_at.isoformat(),
    }
