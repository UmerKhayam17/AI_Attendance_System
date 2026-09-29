import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

import cv2
from django.db import close_old_connections
import numpy as np

from attendance.models import AttendanceRecord
from attendance.services.decision_engine import AttendanceDecisionEngine
from employees.models import Employee
from recognition.models import Camera
from recognition.services.byte_tracker import BYTETracker
from recognition.services.camera_health import mark_stopped, persist_heartbeat
from recognition.services.events import (
    flag_unusual_hours,
    flag_wrong_branch,
    record_event,
    record_spoof,
    record_unknown,
)
from recognition.services.face_engine import CCTV_SIMILARITY_THRESHOLD, get_face_engine
from recognition.services.gallery_index import get_gallery_index
from recognition.services.match_confirm import CONFIRM_CCTV
from recognition.services.matching import REVIEW_MIN_SIMILARITY
from recognition.services.review_queue import enqueue_match_review
from recognition.services.rtsp_utils import open_rtsp_capture
from recognition.services.snapshot_saver import save_detection_snapshot, snapshot_to_dict

logger = logging.getLogger(__name__)

# Skip tiny detections (false positives / unusable for ArcFace)
MIN_FACE_PX = 40
MIN_DET_SCORE = 0.55
# Upscale mid-size faces before embedding (CCTV distance)
UPSCALE_BELOW_PX = 110
UPSCALE_FACTOR = 2.5
# Don't re-mark the same person too often from the same camera
MATCH_COOLDOWN_SEC = 45


@dataclass
class CameraRuntimeState:
    camera_id: int
    name: str
    organization_id: int | None = None
    zone: str = Camera.ZONE_MIXED
    running: bool = False
    connected: bool = False
    last_error: str = ""
    last_frame_at: str | None = None
    frames_processed: int = 0
    gallery_size: int = 0
    last_events: deque = field(default_factory=lambda: deque(maxlen=30))
    last_jpeg: bytes | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    match_cooldown: dict = field(default_factory=dict)
    tracker: BYTETracker = field(default_factory=BYTETracker)
    fps: float = 0.0
    fps_frames: int = 0
    heartbeat_at: float = 0.0


class CCTVWorkerManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._cameras: dict[int, CameraRuntimeState] = {}
        self._scan_interval = 1.5
        self._frame_skip = 8

    def list_status(self) -> list[dict]:
        with self._lock:
            return [self._status_dict(state) for state in self._cameras.values()]

    def get_status(self, camera_id: int) -> dict | None:
        with self._lock:
            state = self._cameras.get(camera_id)
            return self._status_dict(state) if state else None

    def get_snapshot_jpeg(self, camera_id: int) -> bytes | None:
        with self._lock:
            state = self._cameras.get(camera_id)
            return state.last_jpeg if state else None

    def get_events(self, camera_id: int | None = None, limit: int = 40) -> list[dict]:
        with self._lock:
            if camera_id is not None:
                state = self._cameras.get(camera_id)
                if not state:
                    return []
                return list(state.last_events)[:limit]

            events = []
            for state in self._cameras.values():
                events.extend(state.last_events)
            events.sort(key=lambda e: e.get("time", ""), reverse=True)
            return events[:limit]

    def start_camera(
        self,
        camera_id: int,
        name: str,
        rtsp_url: str,
        start_delay: float = 0.0,
        organization_id: int | None = None,
        zone: str = Camera.ZONE_MIXED,
    ) -> dict:
        with self._lock:
            existing = self._cameras.get(camera_id)
            if existing and existing.running:
                existing.zone = zone or existing.zone
                return self._status_dict(existing)

            stop_event = threading.Event()
            state = CameraRuntimeState(
                camera_id=camera_id,
                name=name,
                organization_id=organization_id,
                zone=zone or Camera.ZONE_MIXED,
                stop_event=stop_event,
            )
            thread = threading.Thread(
                target=self._run_camera,
                args=(state, rtsp_url, start_delay),
                name=f"cctv-{camera_id}",
                daemon=True,
            )
            state.thread = thread
            state.running = True
            self._cameras[camera_id] = state
            thread.start()
            return self._status_dict(state)

    def stop_camera(self, camera_id: int) -> dict | None:
        with self._lock:
            state = self._cameras.get(camera_id)
            if not state:
                return None
            state.stop_event.set()
            state.running = False
            thread = state.thread

        if thread and thread.is_alive():
            thread.join(timeout=5)

        mark_stopped(camera_id)
        try:
            from recognition.services.dwell import close_camera

            close_camera(camera_id)
        except Exception:
            pass
        with self._lock:
            state.connected = False
            return self._status_dict(state)

    def start_all(self, cameras: list[dict]) -> list[dict]:
        # Stagger connects so Hikvision NVRs don't return SETUP 500
        return [
            self.start_camera(
                c["id"],
                c["name"],
                c["rtsp_url"],
                start_delay=i * 2.5,
                organization_id=c.get("organization_id"),
                zone=c.get("zone") or Camera.ZONE_MIXED,
            )
            for i, c in enumerate(cameras)
        ]

    def stop_all(self) -> list[dict]:
        with self._lock:
            ids = list(self._cameras.keys())
        results = []
        for cid in ids:
            status = self.stop_camera(cid)
            if status:
                results.append(status)
        return results

    def _status_dict(self, state: CameraRuntimeState) -> dict:
        return {
            "camera_id": state.camera_id,
            "name": state.name,
            "organization_id": state.organization_id,
            "zone": state.zone,
            "running": state.running,
            "connected": state.connected,
            "last_error": state.last_error,
            "last_frame_at": state.last_frame_at,
            "frames_processed": state.frames_processed,
            "gallery_size": state.gallery_size,
            "fps": round(state.fps, 2),
            "health": "online" if state.connected and state.running else ("offline" if state.running else "stopped"),
            "active_tracks": len([t for t in state.tracker.tracks if t.time_since_update == 0]),
            "recent_events": list(state.last_events)[:8],
            "has_snapshot": state.last_jpeg is not None,
        }

    def _build_gallery(self, organization_id: int | None):
        close_old_connections()
        if organization_id is None:
            return {}
        return get_gallery_index(organization_id)

    def _face_bbox_size(self, face) -> tuple[int, int]:
        bbox = getattr(face, "bbox", None)
        if bbox is None:
            return 0, 0
        x1, y1, x2, y2 = [int(v) for v in bbox]
        return max(x2 - x1, 0), max(y2 - y1, 0)

    def _refine_embedding(self, engine, frame, face):
        """
        For mid-size CCTV faces, crop + upscale and re-extract embedding.
        Tiny faces are skipped by the caller; large faces use the original embedding.
        """
        bbox = getattr(face, "bbox", None)
        if bbox is None:
            return face.embedding, self._face_bbox_size(face)

        x1, y1, x2, y2 = [int(v) for v in bbox]
        face_w, face_h = max(x2 - x1, 0), max(y2 - y1, 0)
        if face_w >= UPSCALE_BELOW_PX and face_h >= UPSCALE_BELOW_PX:
            return face.embedding, (face_w, face_h)

        h, w = frame.shape[:2]
        pad = int(max(face_w, face_h) * 0.45)
        cx1 = max(0, x1 - pad)
        cy1 = max(0, y1 - pad)
        cx2 = min(w, x2 + pad)
        cy2 = min(h, y2 + pad)
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return face.embedding, (face_w, face_h)

        up = cv2.resize(
            crop,
            None,
            fx=UPSCALE_FACTOR,
            fy=UPSCALE_FACTOR,
            interpolation=cv2.INTER_CUBIC,
        )
        refined = engine.detect_faces(up)
        if not refined:
            return face.embedding, (face_w, face_h)

        best = max(refined, key=lambda f: float(getattr(f, "det_score", 0.0)))
        if float(getattr(best, "det_score", 0.0)) < MIN_DET_SCORE:
            return face.embedding, (face_w, face_h)
        return best.embedding, (face_w, face_h)

    def _process_tracked_faces(self, state, engine, gallery, frame_infer, faces, now: float):
        close_old_connections()
        usable = []
        dets = []
        for face in faces:
            det_score = float(getattr(face, "det_score", 0.0))
            face_w, face_h = self._face_bbox_size(face)
            if det_score < 0.30 or face_w < MIN_FACE_PX or face_h < MIN_FACE_PX:
                continue
            bbox = [float(v) for v in face.bbox]
            usable.append(face)
            dets.append([bbox[0], bbox[1], bbox[2], bbox[3], det_score])

        tracks = state.tracker.update(np.array(dets, dtype=np.float32) if dets else np.zeros((0, 5)))
        seen_ids: set[str] = set()
        for track in tracks:
            if track.det_index is None or track.det_index >= len(usable):
                continue
            face = usable[track.det_index]
            bbox = getattr(face, "bbox", None)
            face_w, face_h = self._face_bbox_size(face)

            if track.employee_id:
                employee_id = track.employee_id
                confidence = track.identity_confidence
                matched = True
                message = f"Track #{track.track_id} · {employee_id}"
            else:
                live = engine.check_liveness(frame_infer, face, mode="cctv")
                if not live["passed"] and not live.get("skipped"):
                    record_spoof(
                        organization_id=state.organization_id,
                        camera_id=state.camera_id,
                        camera_name=state.name,
                        message=live["message"],
                        extra={"liveness": live.get("score")},
                        frame=frame_infer,
                        bbox=bbox.tolist() if bbox is not None else None,
                        track_id=track.track_id,
                    )
                    state.last_events.appendleft({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "camera_id": state.camera_id,
                        "camera_name": state.name,
                        "organization_id": state.organization_id,
                        "matched": False,
                        "employee_id": None,
                        "confidence": 0.0,
                        "message": live["message"],
                        "track_id": track.track_id,
                        "face_size": f"{face_w}x{face_h}",
                    })
                    continue

                embedding, (face_w, face_h) = self._refine_embedding(
                    engine, frame_infer, face
                )
                match = engine.match_probe(
                    embedding,
                    gallery,
                    threshold=CCTV_SIMILARITY_THRESHOLD,
                )
                if match.matched and match.employee_id:
                    track.employee_id = match.employee_id
                    track.identity_confidence = match.confidence
                    employee_id = match.employee_id
                    confidence = match.confidence
                    matched = True
                    message = f"Track #{track.track_id} identified"
                elif match.needs_review(REVIEW_MIN_SIMILARITY) and not track.review_queued:
                    track.review_queued = True
                    reason = "ambiguous" if match.ambiguous else "low_confidence"
                    enqueue_match_review(
                        organization_id=state.organization_id,
                        suggested_employee_id=match.candidate_id,
                        camera_id=state.camera_id,
                        camera_name=state.name,
                        frame=frame_infer,
                        bbox=bbox.tolist() if bbox is not None else None,
                        confidence=match.confidence,
                        second_best=match.second_best if match.second_best >= 0 else None,
                        reason=reason,
                        track_id=track.track_id,
                        source="cctv",
                    )
                    state.last_events.appendleft({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "camera_id": state.camera_id,
                        "camera_name": state.name,
                        "organization_id": state.organization_id,
                        "matched": False,
                        "employee_id": match.candidate_id,
                        "confidence": round(match.confidence, 4),
                        "message": "Queued for review — " + match.message,
                        "track_id": track.track_id,
                        "attendance": {
                            "action": "review",
                            "message": "Low-confidence match waiting for confirmation",
                            "status": "",
                        },
                        "face_size": f"{face_w}x{face_h}",
                    })
                    continue
                else:
                    if match.confidence < REVIEW_MIN_SIMILARITY or not match.candidate_id:
                        record_unknown(
                            organization_id=state.organization_id,
                            camera_id=state.camera_id,
                            camera_name=state.name,
                            confidence=match.confidence,
                            message="Unknown person",
                            extra={"candidate_id": match.candidate_id},
                            frame=frame_infer,
                            bbox=bbox.tolist() if bbox is not None else None,
                            track_id=track.track_id,
                        )
                    state.last_events.appendleft({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "camera_id": state.camera_id,
                        "camera_name": state.name,
                        "organization_id": state.organization_id,
                        "matched": False,
                        "employee_id": match.candidate_id,
                        "confidence": round(match.confidence, 4),
                        "message": match.message,
                        "track_id": track.track_id,
                        "face_size": f"{face_w}x{face_h}",
                    })
                    continue

            event = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "camera_id": state.camera_id,
                "camera_name": state.name,
                "organization_id": state.organization_id,
                "matched": matched,
                "employee_id": employee_id,
                "confidence": round(confidence, 4),
                "message": message,
                "track_id": track.track_id,
                "face_size": f"{face_w}x{face_h}",
            }

            if track.hits < CONFIRM_CCTV:
                event["attendance"] = {
                    "action": "pending",
                    "message": f"Tracking ({track.hits}/{CONFIRM_CCTV})",
                    "status": "",
                }
                event["message"] = f"Tracking #{track.track_id} ({track.hits}/{CONFIRM_CCTV})"
                state.last_events.appendleft(event)
                continue

            if matched and employee_id:
                try:
                    from recognition.services.dwell import heartbeat

                    dwell = heartbeat(
                        organization_id=state.organization_id,
                        camera_id=state.camera_id,
                        employee_id=employee_id,
                        track_id=track.track_id,
                        confidence=confidence,
                    )
                    if dwell:
                        event["dwell_seconds"] = dwell["seconds"]
                        seen_ids.add(employee_id)
                except Exception:
                    logger.exception("Dwell heartbeat failed on camera %s", state.camera_id)

            last_match = state.match_cooldown.get(employee_id, 0.0)
            if now - last_match < MATCH_COOLDOWN_SEC:
                event["message"] = f"Track #{track.track_id} (cooldown)"
                event["attendance"] = {
                    "action": "ignored",
                    "message": "Duplicate recognition within cooldown",
                    "status": "",
                }
                state.last_events.appendleft(event)
                continue

            if track.attendance_written:
                state.last_events.appendleft(event)
                continue

            state.match_cooldown[employee_id] = now
            close_old_connections()
            employee = Employee.objects.filter(
                employee_id=employee_id,
                is_active=True,
                organization_id=state.organization_id,
            ).first()
            if not employee:
                continue
            decision = AttendanceDecisionEngine.process_recognition(
                employee=employee,
                confidence=confidence,
                source=AttendanceRecord.SOURCE_CCTV,
                zone=state.zone,
            )
            track.attendance_written = True
            event["attendance"] = {
                "action": decision["action"],
                "message": decision["message"],
                "status": decision["record"].status,
            }
            snapshot = save_detection_snapshot(
                employee=employee,
                camera_id=state.camera_id,
                camera_name=state.name,
                frame=frame_infer,
                confidence=confidence,
                attendance_action=decision["action"],
                bbox=bbox.tolist() if bbox is not None else None,
            )
            if snapshot:
                event["snapshot"] = snapshot_to_dict(snapshot)
                event["message"] = (
                    f"Track #{track.track_id} · Camera #{state.camera_id} ({state.name})"
                )
            camera = Camera.objects.select_related("branch").filter(pk=state.camera_id).first()
            record_event(
                organization_id=state.organization_id,
                kind="recognized",
                camera_id=state.camera_id,
                camera_name=state.name,
                employee=employee,
                confidence=confidence,
                message=event["message"],
                attendance_action=decision["action"],
                track_id=track.track_id,
                status="assigned",
            )
            flag_wrong_branch(employee, camera, confidence=confidence, source="cctv")
            flag_unusual_hours(employee, confidence=confidence, camera=camera, source="cctv")
            logger.info(
                "Camera %s track %s: %s -> %s (%.2f)",
                state.camera_id,
                track.track_id,
                employee_id,
                decision["action"],
                confidence,
            )
            state.last_events.appendleft(event)

        from recognition.services.dwell import close_unseen

        if state.camera_id:
            try:
                close_unseen(state.camera_id, seen_ids)
            except Exception:
                logger.exception("Dwell close_unseen failed on camera %s", state.camera_id)

    def _run_camera(self, state: CameraRuntimeState, rtsp_url: str, start_delay: float = 0.0):
        if start_delay > 0:
            state.last_error = f"Waiting {start_delay:.0f}s before connect…"
            if state.stop_event.wait(start_delay):
                state.running = False
                return

        engine = get_face_engine()
        gallery_refresh_at = 0.0
        gallery: dict[str, list[list[float]]] = {}
        gallery_warned = False
        cap = None
        frame_index = 0
        reconnect_delay = 5

        logger.info("Starting CCTV worker for camera %s (%s)", state.camera_id, state.name)

        while not state.stop_event.is_set():
            try:
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                        cap = None
                    state.connected = False
                    state.last_error = "Connecting to RTSP…"
                    cap, info = open_rtsp_capture(rtsp_url)
                    if cap is None:
                        state.last_error = info or "Cannot open RTSP stream"
                        close_old_connections()
                        persist_heartbeat(
                            state.camera_id,
                            running=True,
                            connected=False,
                            last_error=state.last_error,
                            fps=0,
                        )
                        logger.warning(
                            "Camera %s RTSP failed: %s",
                            state.camera_id,
                            state.last_error,
                        )
                        time.sleep(reconnect_delay)
                        continue
                    state.connected = True
                    state.last_error = ""
                    logger.info(
                        "Camera %s connected (%s)",
                        state.camera_id,
                        info,
                    )

                ok, frame = cap.read()
                if not ok or frame is None:
                    state.connected = False
                    state.last_error = "Frame read failed — reconnecting"
                    close_old_connections()
                    persist_heartbeat(
                        state.camera_id,
                        running=True,
                        connected=False,
                        last_error=state.last_error,
                        fps=0,
                    )
                    cap.release()
                    cap = None
                    time.sleep(reconnect_delay)
                    continue

                state.connected = True
                state.last_frame_at = datetime.now().isoformat(timespec="seconds")
                frame_index += 1
                state.fps_frames += 1
                now_mono = time.time()
                if now_mono - state.heartbeat_at >= 10:
                    elapsed = max(now_mono - state.heartbeat_at, 0.001) if state.heartbeat_at else 10
                    state.fps = state.fps_frames / elapsed
                    close_old_connections()
                    persist_heartbeat(
                        state.camera_id,
                        running=True,
                        connected=True,
                        last_error=state.last_error,
                        fps=state.fps,
                        last_frame_at=state.last_frame_at,
                    )
                    state.heartbeat_at = now_mono
                    state.fps_frames = 0

                if frame_index % 3 == 0:
                    small = cv2.resize(frame, (640, 360))
                    ok_jpg, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ok_jpg:
                        state.last_jpeg = buf.tobytes()

                if frame_index % self._frame_skip != 0:
                    continue

                now = time.time()
                if now - gallery_refresh_at > 30:
                    close_old_connections()
                    from organizations.models import Organization

                    org = None
                    if state.organization_id:
                        org = Organization.objects.filter(pk=state.organization_id).first()
                    if not org or not org.is_active or not org.limits().get("cameras"):
                        state.last_error = "Plan does not include CCTV or org is inactive"
                        state.stop_event.set()
                        break
                    gallery = self._build_gallery(state.organization_id)
                    camera = Camera.objects.filter(pk=state.camera_id).only("zone").first()
                    if camera:
                        state.zone = camera.zone
                    gallery_refresh_at = now
                    state.gallery_size = len(gallery)

                if not gallery:
                    state.gallery_size = 0
                    if not gallery_warned:
                        state.last_events.appendleft({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "camera_id": state.camera_id,
                            "camera_name": state.name,
                            "organization_id": state.organization_id,
                            "matched": False,
                            "employee_id": None,
                            "confidence": 0.0,
                            "message": "No trained face gallery — enroll & train employees first",
                        })
                        gallery_warned = True
                    time.sleep(self._scan_interval)
                    continue

                gallery_warned = False

                h, w = frame.shape[:2]
                # 4K streams must stay near 1080p+ or faces shrink and ArcFace fails
                max_w = 1920
                if w > max_w:
                    scale = max_w / w
                    frame_infer = cv2.resize(frame, (max_w, int(h * scale)))
                else:
                    frame_infer = frame

                faces = engine.detect_faces(frame_infer)
                state.frames_processed += 1
                self._process_tracked_faces(
                    state, engine, gallery, frame_infer, faces, now
                )

                time.sleep(self._scan_interval)

            except Exception as exc:
                logger.exception("Camera %s error: %s", state.camera_id, exc)
                state.last_error = str(exc)
                state.connected = False
                if cap is not None:
                    cap.release()
                    cap = None
                time.sleep(reconnect_delay)

        if cap is not None:
            cap.release()
        state.running = False
        state.connected = False
        try:
            from recognition.services.dwell import close_camera

            close_camera(state.camera_id)
        except Exception:
            pass
        logger.info("Stopped CCTV worker for camera %s", state.camera_id)


_manager: CCTVWorkerManager | None = None
_manager_lock = threading.Lock()


def get_cctv_manager() -> CCTVWorkerManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = CCTVWorkerManager()
    return _manager
