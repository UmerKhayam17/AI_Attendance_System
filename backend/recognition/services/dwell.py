"""Accumulate time a recognized employee stays in a CCTV camera view."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from employees.models import Employee
from organizations.localtime import local_date
from recognition.models import CameraDwellSession

STALE_AFTER = timedelta(seconds=8)
WRITE_EVERY = timedelta(seconds=1.5)


def _seconds(started, ended) -> int:
    if started is None or ended is None:
        return 0
    return max(0, int((ended - started).total_seconds()))


def serialize_session(session: CameraDwellSession, now=None) -> dict:
    now = now or timezone.now()
    end = session.ended_at or now
    employee = session.employee
    camera = session.camera
    return {
        "id": session.id,
        "employee_id": employee.employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
        "camera_id": session.camera_id,
        "camera_name": camera.name if camera else "",
        "started_at": session.started_at.isoformat(),
        "last_seen_at": session.last_seen_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "seconds": _seconds(session.started_at, end),
        "active": session.ended_at is None,
        "confidence": session.peak_confidence,
    }


def heartbeat(*, organization_id: int, camera_id: int, employee_id: str, track_id: int | None, confidence: float = 0):
    employee = Employee.objects.filter(
        organization_id=organization_id,
        employee_id=employee_id,
        is_active=True,
    ).first()
    if employee is None:
        return None
    now = timezone.now()
    session = (
        CameraDwellSession.objects.filter(
            camera_id=camera_id,
            employee=employee,
            ended_at__isnull=True,
        )
        .select_related("employee", "camera")
        .first()
    )
    if session is None:
        session = CameraDwellSession.objects.create(
            organization_id=organization_id,
            camera_id=camera_id,
            employee=employee,
            track_id=track_id,
            started_at=now,
            last_seen_at=now,
            seconds=0,
            peak_confidence=float(confidence or 0),
        )
        session = CameraDwellSession.objects.select_related("employee", "camera").get(pk=session.pk)
        return serialize_session(session, now)

    if now - session.last_seen_at < WRITE_EVERY:
        return serialize_session(session, now)

    session.track_id = track_id
    session.last_seen_at = now
    session.seconds = _seconds(session.started_at, now)
    if confidence:
        session.peak_confidence = max(session.peak_confidence or 0, float(confidence))
    session.save(update_fields=["track_id", "last_seen_at", "seconds", "peak_confidence"])
    return serialize_session(session, now)


def close_unseen(camera_id: int, _seen_employee_ids: set[str] | None = None):
    now = timezone.now()
    cutoff = now - STALE_AFTER
    qs = CameraDwellSession.objects.filter(
        camera_id=camera_id,
        ended_at__isnull=True,
        last_seen_at__lt=cutoff,
    )
    for session in qs:
        session.ended_at = session.last_seen_at
        session.seconds = _seconds(session.started_at, session.ended_at)
        session.save(update_fields=["ended_at", "seconds"])


def close_camera(camera_id: int):
    now = timezone.now()
    qs = CameraDwellSession.objects.filter(camera_id=camera_id, ended_at__isnull=True)
    for session in qs:
        session.ended_at = session.last_seen_at or now
        session.seconds = _seconds(session.started_at, session.ended_at)
        session.save(update_fields=["ended_at", "seconds"])


def overview_for(organization) -> dict:
    now = timezone.now()
    today = local_date(organization=organization)
    active = (
        CameraDwellSession.objects.filter(organization=organization, ended_at__isnull=True)
        .select_related("employee", "camera")
        .order_by("-last_seen_at")
    )
    today_rows = CameraDwellSession.objects.filter(
        organization=organization,
        started_at__date=today,
    ).select_related("employee")
    totals: dict[str, dict] = {}
    for session in today_rows:
        end = session.ended_at or now
        key = session.employee.employee_id
        row = totals.setdefault(
            key,
            {
                "employee_id": key,
                "employee_name": f"{session.employee.first_name} {session.employee.last_name}".strip(),
                "seconds": 0,
            },
        )
        row["seconds"] += _seconds(session.started_at, end)
    return {
        "active": [serialize_session(s, now) for s in active],
        "today": sorted(totals.values(), key=lambda r: r["seconds"], reverse=True),
    }
