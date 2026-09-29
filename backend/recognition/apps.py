import logging
import os
import sys
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RecognitionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recognition"

    def ready(self):
        if not self._should_autostart_cameras():
            return

        thread = threading.Thread(
            target=self._autostart_cameras,
            name="cctv-autostart",
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _should_autostart_cameras() -> bool:
        from django.conf import settings

        if not getattr(settings, "CCTV_AUTOSTART", True):
            return False

        skip_commands = {
            "migrate",
            "makemigrations",
            "test",
            "shell",
            "createsuperuser",
            "collectstatic",
            "seed_cameras",
            "check",
        }
        if any(cmd in sys.argv for cmd in skip_commands):
            return False

        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            if "--noreload" in sys.argv:
                return True
            return False

        return True

    @staticmethod
    def _autostart_cameras():
        time.sleep(2)
        try:
            from django.db import close_old_connections

            close_old_connections()
            from organizations.models import Organization
            from recognition.models import Camera
            from recognition.services.cctv_worker import get_cctv_manager

            manager = get_cctv_manager()
            orgs = Organization.objects.filter(is_active=True)
            started = 0
            for org in orgs:
                quota = int(org.limits().get("cameras") or 0)
                if quota <= 0:
                    continue
                cameras = list(
                    Camera.objects.filter(organization=org, is_active=True)
                    .order_by("sort_order", "id")[:quota]
                    .values("id", "name", "rtsp_url", "organization_id", "zone")
                )
                if not cameras:
                    continue
                manager.start_all(cameras)
                started += len(cameras)

            logger.info("CCTV autostart: started %s camera(s)", started)
        except Exception:
            logger.exception("CCTV autostart failed")
