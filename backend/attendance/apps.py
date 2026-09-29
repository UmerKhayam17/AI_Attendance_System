from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attendance"

    def ready(self):
        from attendance.services.scheduler import start_alert_scheduler

        start_alert_scheduler()
