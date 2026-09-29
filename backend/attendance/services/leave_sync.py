from attendance.models import AttendanceRecord, LeaveRequest
from attendance.services.workday import daterange, is_non_working


def sync_leave_records(leave: LeaveRequest) -> int:
    """Create on-leave attendance rows for approved leave (skip days they already punched)."""
    if leave.status != LeaveRequest.STATUS_APPROVED:
        return 0
    employee = leave.employee
    org = employee.organization
    written = 0
    for day in daterange(leave.start_date, leave.end_date):
        off, _ = is_non_working(org, day)
        if off:
            continue
        record, created = AttendanceRecord.objects.get_or_create(
            employee=employee,
            date=day,
            defaults={
                "status": AttendanceRecord.STATUS_ON_LEAVE,
                "source": AttendanceRecord.SOURCE_MANUAL,
                "notes": f"Leave ({leave.get_leave_type_display()})",
            },
        )
        if record.check_in is None and record.status != AttendanceRecord.STATUS_ON_LEAVE:
            record.status = AttendanceRecord.STATUS_ON_LEAVE
            if not record.notes:
                record.notes = f"Leave ({leave.get_leave_type_display()})"
            record.save(update_fields=["status", "notes", "updated_at"])
            written += 1
        elif created:
            written += 1
    return written
