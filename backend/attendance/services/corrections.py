from django.utils import timezone

from approvals.lock import assert_dates_unlocked
from attendance.models import AttendanceRecord, AttendanceCorrection
from attendance.services.decision_engine import AttendanceDecisionEngine
from attendance.services.shift_rules import apply_checkout_rules, refresh_missing_checkout


def apply_correction(row: AttendanceCorrection, user, reason: str = "") -> AttendanceRecord:
    employee = row.employee
    org = employee.organization
    assert_dates_unlocked(org, row.date, row.date)
    record, _ = AttendanceRecord.objects.get_or_create(
        employee=employee,
        date=row.date,
        defaults={"source": AttendanceRecord.SOURCE_MANUAL},
    )
    if row.requested_check_in:
        record.check_in = row.requested_check_in
        record.status = AttendanceDecisionEngine.determine_status(
            row.requested_check_in, employee=employee, organization=org
        )
    if row.requested_check_out:
        record.check_out = row.requested_check_out
        record.missing_checkout = False
        if record.check_in:
            apply_checkout_rules(record, employee=employee, now=row.requested_check_out)
        else:
            refresh_missing_checkout(record, employee=employee, now=row.requested_check_out)
    record.source = AttendanceRecord.SOURCE_MANUAL
    note = reason or row.reason
    if note:
        prefix = f"Correction: {note}"
        record.notes = prefix if not record.notes else f"{record.notes}\n{prefix}"
    record.save()
    row.status = AttendanceCorrection.STATUS_APPROVED
    row.decided_by = user
    row.applied_at = timezone.now()
    row.save(update_fields=["status", "decided_by", "applied_at", "updated_at"])
    try:
        from approvals.audit import write_audit

        write_audit(
            organization=org,
            actor=user,
            action="correction.applied",
            model="AttendanceCorrection",
            object_id=row.id,
            old_value=row.original_snapshot(),
            new_value={
                "check_in": record.check_in.isoformat() if record.check_in else None,
                "check_out": record.check_out.isoformat() if record.check_out else None,
                "status": record.status,
            },
            reason=row.reason or reason,
        )
    except Exception:
        pass
    return record
