from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from attendance.models import AttendanceRecord
from attendance.services.decision_engine import AttendanceDecisionEngine
from employees.models import Department, Employee
from organizations.models import Branch, Organization
from recognition.models import Camera, RecognitionEvent
from recognition.services.camera_health import health_from_runtime, persist_heartbeat
from recognition.services.events import flag_wrong_branch, record_unknown
from recognition.services.antispoof import crop_with_scale, screen_moire_score
from recognition.services.match_confirm import MatchConfirmer
from recognition.services.matching import best_match

import numpy as np


def _unit(seed: int, dim: int = 8) -> list[float]:
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=dim).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


class MatchingTests(SimpleTestCase):
    def test_nearest_embedding_wins_over_mean_style_collision(self):
        probe = _unit(1)
        gallery = {
            "emp001": [_unit(9), probe, _unit(10)],
            "emp002": [_unit(2)],
        }
        result = best_match(probe, gallery, threshold=0.4, margin=0.05)
        self.assertTrue(result.matched)
        self.assertEqual(result.employee_id, "emp001")

    def test_legacy_single_vector_still_matches(self):
        probe = _unit(3)
        result = best_match(probe, {"emp001": probe}, threshold=0.4)
        self.assertEqual(result.employee_id, "emp001")

    def test_ambiguous_identities_are_rejected(self):
        probe = _unit(4)
        close = np.array(_unit(4), dtype=np.float32)
        close = close + np.array(_unit(5), dtype=np.float32) * 0.02
        close = (close / np.linalg.norm(close)).tolist()
        result = best_match(
            probe,
            {"emp001": [probe], "emp002": [close]},
            threshold=0.3,
            margin=0.08,
        )
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.employee_id)

    def test_below_threshold_is_unknown(self):
        result = best_match(_unit(1), {"emp001": [_unit(99)]}, threshold=0.99)
        self.assertFalse(result.matched)
        self.assertFalse(result.ambiguous)


class MatchConfirmTests(SimpleTestCase):
    def test_requires_consecutive_hits(self):
        confirmer = MatchConfirmer()
        first = confirmer.observe(
            organization_id=1,
            source_key="cam:1",
            employee_id="emp001",
            required=3,
            window_sec=12,
            now=100.0,
        )
        self.assertFalse(first.confirmed)
        self.assertEqual(first.hits, 1)
        second = confirmer.observe(
            organization_id=1,
            source_key="cam:1",
            employee_id="emp001",
            required=3,
            window_sec=12,
            now=102.0,
        )
        self.assertFalse(second.confirmed)
        third = confirmer.observe(
            organization_id=1,
            source_key="cam:1",
            employee_id="emp001",
            required=3,
            window_sec=12,
            now=104.0,
        )
        self.assertTrue(third.confirmed)

    def test_identity_switch_resets_window(self):
        confirmer = MatchConfirmer()
        confirmer.observe(
            organization_id=1, source_key="webcam", employee_id="a", required=2, now=1.0
        )
        switched = confirmer.observe(
            organization_id=1, source_key="webcam", employee_id="b", required=2, now=2.0
        )
        self.assertFalse(switched.confirmed)
        self.assertEqual(switched.hits, 1)


class AntiSpoofHelperTests(SimpleTestCase):
    def test_crop_with_scale_returns_80px(self):
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        crop = crop_with_scale(image, (100, 80, 160, 160), scale=2.7, size=80)
        self.assertIsNotNone(crop)
        self.assertEqual(crop.shape, (80, 80, 3))

    def test_striped_image_has_higher_moire_than_smooth(self):
        smooth = np.full((80, 80, 3), 120, dtype=np.uint8)
        striped = np.zeros((80, 80, 3), dtype=np.uint8)
        striped[:, ::2] = 255
        self.assertGreater(screen_moire_score(striped), screen_moire_score(smooth))


class CameraZoneDecisionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Trust Co", slug="trust-co")
        engineering = Department.objects.create(organization=self.org, name="Engineering")
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="emp100",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@trust.test",
            department=engineering,
            designation="Engineer",
        )
        self.t0 = timezone.now()

    def test_entry_camera_does_not_check_out(self):
        first = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.91, zone=Camera.ZONE_ENTRY, now=self.t0
        )
        self.assertEqual(first["action"], "check_in")
        later = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.92, zone=Camera.ZONE_ENTRY, now=self.t0 + timedelta(hours=8)
        )
        self.assertEqual(later["action"], "ignored")
        record = AttendanceRecord.objects.get(employee=self.employee)
        self.assertIsNone(record.check_out)

    def test_exit_camera_requires_check_in(self):
        result = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_EXIT, now=self.t0
        )
        self.assertEqual(result["action"], "ignored")
        self.assertIsNone(result["record"].check_in)

    def test_exit_camera_checks_out_after_entry(self):
        AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_ENTRY, now=self.t0
        )
        result = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.88, zone=Camera.ZONE_EXIT, now=self.t0 + timedelta(hours=8)
        )
        self.assertEqual(result["action"], "check_out")
        record = AttendanceRecord.objects.get(employee=self.employee)
        self.assertIsNotNone(record.check_out)

    def test_interior_checks_in_but_never_out(self):
        first = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_INTERIOR, now=self.t0
        )
        self.assertEqual(first["action"], "check_in")
        later = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_INTERIOR, now=self.t0 + timedelta(hours=3)
        )
        self.assertEqual(later["action"], "ignored")

    def test_mixed_keeps_first_in_last_out(self):
        AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_MIXED, now=self.t0
        )
        AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone=Camera.ZONE_MIXED, now=self.t0 + timedelta(hours=9)
        )
        record = AttendanceRecord.objects.get(employee=self.employee)
        self.assertIsNotNone(record.check_in)
        self.assertIsNotNone(record.check_out)


class ByteTrackTests(SimpleTestCase):
    def test_overlapping_boxes_keep_the_same_id(self):
        from recognition.services.byte_tracker import BYTETracker

        tracker = BYTETracker(track_high_thresh=0.5, match_iou=0.3, max_time_lost=5)
        first = tracker.update(np.array([[10, 10, 80, 80, 0.9]], dtype=np.float32))
        second = tracker.update(np.array([[14, 12, 84, 82, 0.88]], dtype=np.float32))
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0].track_id, second[0].track_id)
        self.assertGreaterEqual(second[0].hits, 2)

    def test_distant_box_starts_a_new_track(self):
        from recognition.services.byte_tracker import BYTETracker

        tracker = BYTETracker(track_high_thresh=0.5, match_iou=0.3)
        first = tracker.update(np.array([[10, 10, 50, 50, 0.9]], dtype=np.float32))
        second = tracker.update(np.array([[400, 300, 460, 360, 0.9]], dtype=np.float32))
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0].track_id, second[0].track_id)


class ReviewBandTests(SimpleTestCase):
    def test_near_miss_is_flagged_for_review(self):
        probe = _unit(7)
        other = _unit(8)
        result = best_match(probe, {"emp001": [other]}, threshold=0.95, margin=0.2)
        self.assertFalse(result.matched)
        self.assertEqual(result.candidate_id, "emp001")
        self.assertTrue(result.needs_review(review_min=0.0))


class GalleryIndexTests(SimpleTestCase):
    def test_index_agrees_with_dict_gallery(self):
        from recognition.services.gallery_index import build_index

        probe = _unit(1)
        gallery = {
            "emp001": [_unit(9), probe, _unit(10)],
            "emp002": [_unit(2)],
        }
        indexed = build_index(gallery)
        a = best_match(probe, gallery, threshold=0.4, margin=0.05)
        b = best_match(probe, indexed, threshold=0.4, margin=0.05)
        self.assertEqual(a.employee_id, b.employee_id)
        self.assertTrue(b.matched)


class Phase3EventsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="AI Co", slug="ai-co-p3")
        self.home = self.org.default_branch()
        self.away = Branch.objects.create(organization=self.org, name="Lahore", timezone="Asia/Karachi")
        engineering = Department.objects.create(organization=self.org, name="Security", branch=self.home)
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="emp200",
            first_name="Ahmed",
            last_name="Khan",
            email="ahmed@ai.test",
            department=engineering,
            designation="Guard",
            branch=self.home,
        )
        self.camera = Camera.objects.create(
            organization=self.org,
            name="Main Gate",
            rtsp_url="rtsp://example/stream",
            branch=self.away,
        )

    def test_unknown_is_recorded_once_per_cooldown(self):
        first = record_unknown(
            organization_id=self.org.id,
            camera_id=self.camera.id,
            camera_name=self.camera.name,
            message="Unknown person",
            track_id=7,
        )
        second = record_unknown(
            organization_id=self.org.id,
            camera_id=self.camera.id,
            camera_name=self.camera.name,
            message="Unknown person",
            track_id=7,
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(RecognitionEvent.objects.filter(kind=RecognitionEvent.KIND_UNKNOWN).count(), 1)

    def test_wrong_branch_creates_anomaly(self):
        event = flag_wrong_branch(self.employee, self.camera, confidence=0.9, source="cctv")
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, RecognitionEvent.KIND_ANOMALY)
        self.assertEqual(event.extra.get("code"), "wrong_branch")

    def test_camera_health_offline_when_disconnected(self):
        self.assertEqual(health_from_runtime(None, self.camera), Camera.HEALTH_STOPPED)
        self.assertEqual(
            health_from_runtime({"running": True, "connected": False, "last_error": "lost"}, self.camera),
            Camera.HEALTH_OFFLINE,
        )
        self.assertEqual(
            health_from_runtime({"running": True, "connected": True, "last_error": "", "fps": 8}, self.camera),
            Camera.HEALTH_ONLINE,
        )

    def test_offline_transition_writes_camera_event(self):
        Camera.objects.filter(pk=self.camera.id).update(health_status=Camera.HEALTH_ONLINE)
        persist_heartbeat(self.camera.id, running=True, connected=False, last_error="RTSP lost", fps=0)
        self.camera.refresh_from_db()
        self.assertEqual(self.camera.health_status, Camera.HEALTH_OFFLINE)
        self.assertTrue(
            RecognitionEvent.objects.filter(
                organization=self.org,
                kind=RecognitionEvent.KIND_CAMERA,
                camera=self.camera,
            ).exists()
        )


class DwellTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Dwell Co", slug="dwell-co-cam")
        self.branch = self.org.default_branch()
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="d1",
            first_name="Noor",
            last_name="Ali",
            email="noor@dwell.test",
            designation="Staff",
            branch=self.branch,
        )
        self.camera = Camera.objects.create(
            organization=self.org,
            name="Lobby",
            rtsp_url="rtsp://example/lobby",
            branch=self.branch,
        )

    def test_heartbeat_keeps_one_open_session(self):
        from recognition.models import CameraDwellSession
        from recognition.services.dwell import heartbeat

        first = heartbeat(
            organization_id=self.org.id,
            camera_id=self.camera.id,
            employee_id="d1",
            track_id=3,
            confidence=0.9,
        )
        self.assertTrue(first["active"])
        session = CameraDwellSession.objects.get()
        started = timezone.now() - timedelta(seconds=4)
        session.started_at = started
        session.last_seen_at = started
        session.save(update_fields=["started_at", "last_seen_at"])
        second = heartbeat(
            organization_id=self.org.id,
            camera_id=self.camera.id,
            employee_id="d1",
            track_id=3,
            confidence=0.91,
        )
        self.assertEqual(CameraDwellSession.objects.count(), 1)
        self.assertGreaterEqual(second["seconds"], 4)

    def test_stale_view_closes_session(self):
        from recognition.models import CameraDwellSession
        from recognition.services.dwell import close_unseen, heartbeat

        heartbeat(
            organization_id=self.org.id,
            camera_id=self.camera.id,
            employee_id="d1",
            track_id=1,
            confidence=0.8,
        )
        CameraDwellSession.objects.update(
            started_at=timezone.now() - timedelta(seconds=30),
            last_seen_at=timezone.now() - timedelta(seconds=20),
        )
        close_unseen(self.camera.id)
        row = CameraDwellSession.objects.get()
        self.assertIsNotNone(row.ended_at)
        self.assertGreater(row.seconds, 0)

