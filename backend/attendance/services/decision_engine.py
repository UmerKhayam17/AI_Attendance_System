from datetime import datetime, timedelta

from attendance.models import AttendanceRecord
from attendance.services.school_webhook import notify_school
from attendance.services.shift_rules import apply_checkout_rules, refresh_missing_checkout
from organizations.localtime import as_local, local_date
from organizations.shifts import is_on_time, schedule_for

ZONE_MIXED = "mixed"
ZONE_ENTRY = "entry"
ZONE_EXIT = "exit"
ZONE_INTERIOR = "interior"


class AttendanceDecisionEngine:
    MIN_CHECKOUT_AFTER_IN = timedelta(minutes=1)

    @classmethod
    def determine_status(cls, check_in_time: datetime, employee=None, organization=None) -> str:
        organization = organization or getattr(employee, "organization", None)
        schedule = schedule_for(employee=employee, organization=organization)
        if getattr(schedule, "kind", "fixed") == "flexible":
            return AttendanceRecord.STATUS_PRESENT
        local_time = as_local(check_in_time, employee=employee, organization=organization).time()
        if is_on_time(local_time, schedule.start_time, schedule.late_after):
            return AttendanceRecord.STATUS_PRESENT
        return AttendanceRecord.STATUS_LATE

    @classmethod
    def process_recognition(
        cls,
        employee,
        confidence: float,
        source: str = AttendanceRecord.SOURCE_CCTV,
        now: datetime | None = None,
        zone: str = ZONE_MIXED,
        latitude=None,
        longitude=None,
    ) -> dict:
        from django.utils import timezone

        now = now or timezone.now()
        organization = getattr(employee, "organization", None)
        today = local_date(employee=employee, organization=organization, now=now)
        zone = zone or ZONE_MIXED

        record, _ = AttendanceRecord.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={"source": source},
        )

        if record.check_in is None:
            if zone == ZONE_EXIT:
                return {
                    "action": "ignored",
                    "message": "Exit camera — no check-in recorded yet",
                    "record": record,
                }
            record.check_in = now
            record.check_in_confidence = confidence
            record.status = cls.determine_status(now, employee=employee, organization=organization)
            record.source = source
            if latitude is not None:
                record.latitude = latitude
                record.longitude = longitude
            record.missing_checkout = False
            record.save(update_fields=[
                "check_in", "check_in_confidence", "status", "source",
                "latitude", "longitude", "missing_checkout", "updated_at"
            ])
            result = {
                "action": "check_in",
                "message": f"Checked in at {as_local(now, employee=employee).strftime('%H:%M')}",
                "record": record,
            }
            notify_school(record, "check_in")
            if record.status == AttendanceRecord.STATUS_LATE:
                from attendance.services.notifier import notify_event_async

                notify_event_async(employee.id, "late", record.id)
            return result

        if zone in (ZONE_ENTRY, ZONE_INTERIOR):
            refresh_missing_checkout(record, employee=employee, now=now)
            record.save(update_fields=["missing_checkout", "updated_at"])
            return {
                "action": "ignored",
                "message": "Already checked in — this camera does not check out",
                "record": record,
            }

        if now - record.check_in < cls.MIN_CHECKOUT_AFTER_IN:
            return {
                "action": "ignored",
                "message": "Checked in just now — waiting before first check-out update",
                "record": record,
            }

        record.check_out = now
        record.check_out_confidence = confidence
        if latitude is not None:
            record.latitude = latitude
            record.longitude = longitude
        apply_checkout_rules(record, employee=employee, now=now)
        record.save(update_fields=[
            "check_out",
            "check_out_confidence",
            "status",
            "overtime_minutes",
            "early_leave",
            "missing_checkout",
            "latitude",
            "longitude",
            "updated_at",
        ])
        extras = []
        if record.status == AttendanceRecord.STATUS_HALF_DAY:
            extras.append("half day")
        elif record.early_leave:
            extras.append("early leave")
        if record.overtime_minutes:
            extras.append(f"{record.overtime_minutes} min overtime")
        suffix = f" ({', '.join(extras)})" if extras else ""
        result = {
            "action": "check_out",
            "message": f"Check-out updated to {as_local(now, employee=employee).strftime('%H:%M')}{suffix}",
            "record": record,
        }
        notify_school(record, "check_out")
        return result
