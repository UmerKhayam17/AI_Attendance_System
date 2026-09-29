import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from organizations.models import Organization
from recognition.models import Camera
from recognition.services.cctv_worker import get_cctv_manager


class Command(BaseCommand):
    help = "Run CCTV workers in a dedicated process (one InsightFace session + gallery index)."

    def handle(self, *args, **options):
        manager = get_cctv_manager()
        self.stdout.write("CCTV worker process started. Ctrl+C to stop.")
        try:
            while True:
                close_old_connections()
                started = 0
                for org in Organization.objects.filter(is_active=True):
                    quota = int(org.limits().get("cameras") or 0)
                    if quota <= 0:
                        continue
                    cameras = list(
                        Camera.objects.filter(organization=org, is_active=True)
                        .order_by("sort_order", "id")[:quota]
                        .values("id", "name", "rtsp_url", "organization_id", "zone")
                    )
                    if cameras:
                        manager.start_all(cameras)
                        started += len(cameras)
                self.stdout.write(f"Cameras running: {started}")
                time.sleep(30)
        except KeyboardInterrupt:
            manager.stop_all()
            self.stdout.write("Stopped.")
