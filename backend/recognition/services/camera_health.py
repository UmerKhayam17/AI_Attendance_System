from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from recognition.models import Camera, RecognitionEvent

STALE_SECONDS = 25
ALERT_COOLDOWN = timedelta(hours=1)


def health_from_runtime(runtime: dict | None, camera: Camera | None = None) -> str:
    if runtime and runtime.get("running"):
        if not runtime.get("connected"):
            return Camera.HEALTH_OFFLINE
        last = runtime.get("last_frame_at")
        if last:
            parsed = parse_datetime(last) if isinstance(last, str) else last
            if parsed is not None:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                if (timezone.now() - parsed).total_seconds() > STALE_SECONDS:
                    return Camera.HEALTH_OFFLINE
        error = (runtime.get("last_error") or "").strip()
        fps = runtime.get("fps")
        if error or (fps is not None and fps < 0.4):
            return Camera.HEALTH_DEGRADED
        return Camera.HEALTH_ONLINE

    if camera and camera.last_heartbeat_at:
        age = (timezone.now() - camera.last_heartbeat_at).total_seconds()
        if age > STALE_SECONDS * 2 and camera.health_status in (
            Camera.HEALTH_ONLINE,
            Camera.HEALTH_DEGRADED,
        ):
            return Camera.HEALTH_OFFLINE
        return camera.health_status or Camera.HEALTH_STOPPED
    return Camera.HEALTH_STOPPED


def persist_heartbeat(
    camera_id: int,
    *,
    running: bool,
    connected: bool,
    last_error: str = "",
    fps: float | None = None,
    last_frame_at: str | None = None,
):
    camera = Camera.objects.filter(pk=camera_id).select_related("organization").first()
    if camera is None:
        return None
    previous = camera.health_status
    runtime = {
        "running": running,
        "connected": connected,
        "last_error": last_error,
        "fps": fps,
        "last_frame_at": last_frame_at,
    }
    status = health_from_runtime(runtime, camera)
    Camera.objects.filter(pk=camera_id).update(
        health_status=status,
        last_heartbeat_at=timezone.now(),
        last_error=(last_error or "")[:250],
        fps=fps,
    )
    camera.health_status = status
    camera.last_error = (last_error or "")[:250]
    camera.fps = fps
    if previous in (Camera.HEALTH_ONLINE, Camera.HEALTH_DEGRADED) and status == Camera.HEALTH_OFFLINE:
        _alert_offline(camera)
    return status


def mark_stopped(camera_id: int):
    Camera.objects.filter(pk=camera_id).update(
        health_status=Camera.HEALTH_STOPPED,
        last_heartbeat_at=timezone.now(),
        fps=0,
    )


def _alert_offline(camera: Camera):
    now = timezone.now()
    if camera.last_health_alert_at and now - camera.last_health_alert_at < ALERT_COOLDOWN:
        return
    Camera.objects.filter(pk=camera.id).update(last_health_alert_at=now)
    RecognitionEvent.objects.create(
        organization_id=camera.organization_id,
        camera=camera,
        kind=RecognitionEvent.KIND_CAMERA,
        camera_name=camera.name,
        message=f"{camera.name} went offline",
        extra={"code": "camera_offline", "last_error": camera.last_error},
        source="system",
    )
    try:
        from approvals.notify import notify_async, notify_users, staff_users

        org = camera.organization
        users = staff_users(org)

        def _send():
            notify_users(
                org,
                users,
                kind="camera",
                title=f"Camera offline: {camera.name}",
                body=camera.last_error or "No frames received",
                link="/settings/cameras",
            )

        notify_async(_send)
    except Exception:
        pass


def camera_health_summary(organization, runtime_by_id: dict | None = None) -> dict:
    cameras = list(Camera.objects.filter(organization=organization, is_active=True))
    counts = {Camera.HEALTH_ONLINE: 0, Camera.HEALTH_DEGRADED: 0, Camera.HEALTH_OFFLINE: 0, Camera.HEALTH_STOPPED: 0}
    for cam in cameras:
        runtime = (runtime_by_id or {}).get(cam.id)
        status = health_from_runtime(runtime, cam)
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(cameras),
        "online": counts[Camera.HEALTH_ONLINE],
        "degraded": counts[Camera.HEALTH_DEGRADED],
        "offline": counts[Camera.HEALTH_OFFLINE],
        "stopped": counts[Camera.HEALTH_STOPPED],
    }
