import logging
import os
import sys
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organizations"

    def ready(self):
        if not self._should_bootstrap():
            return
        thread = threading.Thread(
            target=self._bootstrap,
            name="superadmin-bootstrap",
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _should_bootstrap() -> bool:
        skip = {
            "migrate",
            "makemigrations",
            "test",
            "shell",
            "createsuperuser",
            "collectstatic",
            "check",
        }
        if any(cmd in sys.argv for cmd in skip):
            return False
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return "--noreload" in sys.argv
        return True

    @staticmethod
    def _bootstrap():
        time.sleep(1)
        try:
            from django.db import close_old_connections

            close_old_connections()
            from organizations.bootstrap import ensure_superadmin

            ensure_superadmin()
        except Exception:
            logger.exception("Super admin bootstrap failed")
