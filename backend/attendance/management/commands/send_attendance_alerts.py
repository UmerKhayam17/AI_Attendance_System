from django.core.management.base import BaseCommand

from attendance.services.alerts import send_absent_alerts


class Command(BaseCommand):
    help = "Send absent alerts for people still missing after late_after."

    def handle(self, *args, **options):
        sent = send_absent_alerts()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} absent alert channel(s)"))
