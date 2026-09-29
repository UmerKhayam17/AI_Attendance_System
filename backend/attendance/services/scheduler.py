"""Optional in-process late/absent alert loop for runserver."""
from __future__ import annotations

import logging
import os
import sys
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)
_started = False


def _should_start() -> bool:
    enabled = str(getattr(settings, "ALERT_SCHEDULER", True)).lower() in ("1", "true", "yes", "on")
    if not enabled:
        return False
    skip = {
        "migrate",
        "makemigrations",
        "test",
        "shell",
        "createsuperuser",
        "collectstatic",
        "check",
        "run_cctv_worker",
    }
    if any(cmd in sys.argv for cmd in skip):
        return False
    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        return "--noreload" in sys.argv
    return True


def start_alert_scheduler():
    global _started
    if _started or not _should_start():
        return
    _started = True
    thread = threading.Thread(target=_loop, name="attendance-alerts", daemon=True)
    thread.start()


def _loop():
    interval = int(getattr(settings, "ALERT_INTERVAL_SEC", 300))
    time.sleep(20)
    while True:
        try:
            from django.db import close_old_connections

            close_old_connections()
            from attendance.services.alerts import send_absent_alerts

            sent = send_absent_alerts()
            if sent:
                logger.info("Absent alerts sent: %s", sent)
        except Exception:
            logger.exception("Absent alert scheduler failed")
        time.sleep(max(interval, 60))
