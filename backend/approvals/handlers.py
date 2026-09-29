"""Finalize domain objects when an approval request completes."""
from approvals.audit import write_audit
from approvals.lock import assert_dates_unlocked
from approvals.models import ApprovalWorkflow


def on_final(req, user, comment: str, *, approved: bool):
    if req.kind == ApprovalWorkflow.KIND_LEAVE:
        _leave(req, user, comment, approved)
    elif req.kind == ApprovalWorkflow.KIND_CORRECTION:
        _correction(req, user, comment, approved)
    elif req.kind == ApprovalWorkflow.KIND_OVERTIME:
        _overtime(req, user, comment, approved)
    elif req.kind == ApprovalWorkflow.KIND_EXIT:
        _exit(req, user, comment, approved)


def _leave(req, user, comment, approved):
    from attendance.models import LeaveRequest
    from attendance.services.leave_sync import sync_leave_records
    from payroll.services.leave_policy import assert_leave_allowed

    leave = LeaveRequest.objects.select_related("employee", "employee__organization").filter(pk=req.target_id).first()
    if leave is None:
        return
    if approved:
        assert_dates_unlocked(leave.employee.organization, leave.start_date, leave.end_date)
        assert_leave_allowed(leave)
        leave.status = LeaveRequest.STATUS_APPROVED
        leave.decided_by = user
        leave.save(update_fields=["status", "decided_by", "updated_at"])
        sync_leave_records(leave)
    else:
        leave.status = LeaveRequest.STATUS_REJECTED
        leave.decided_by = user
        leave.save(update_fields=["status", "decided_by", "updated_at"])
    write_audit(
        organization=req.organization,
        actor=user,
        action="leave.approved" if approved else "leave.rejected",
        model="LeaveRequest",
        object_id=leave.id,
        new_value={"status": leave.status, "comment": comment},
        reason=comment,
    )


def _correction(req, user, comment, approved):
    from attendance.models import AttendanceCorrection
    from attendance.services.corrections import apply_correction

    row = AttendanceCorrection.objects.select_related("employee").filter(pk=req.target_id).first()
    if row is None:
        return
    if approved:
        apply_correction(row, user, reason=comment)
    else:
        row.status = AttendanceCorrection.STATUS_REJECTED
        row.decided_by = user
        row.save(update_fields=["status", "decided_by", "updated_at"])
    write_audit(
        organization=req.organization,
        actor=user,
        action="correction.applied" if approved else "correction.rejected",
        model="AttendanceCorrection",
        object_id=row.id,
        old_value=row.original_snapshot(),
        new_value={
            "check_in": row.requested_check_in.isoformat() if row.requested_check_in else None,
            "check_out": row.requested_check_out.isoformat() if row.requested_check_out else None,
        },
        reason=row.reason or comment,
    )


def _overtime(req, user, comment, approved):
    from attendance.models import OvertimeRequest

    row = OvertimeRequest.objects.filter(pk=req.target_id).first()
    if row is None:
        return
    row.status = OvertimeRequest.STATUS_APPROVED if approved else OvertimeRequest.STATUS_REJECTED
    row.decided_by = user
    row.save(update_fields=["status", "decided_by", "updated_at"])
    write_audit(
        organization=req.organization,
        actor=user,
        action="overtime.approved" if approved else "overtime.rejected",
        model="OvertimeRequest",
        object_id=row.id,
        new_value={"minutes": row.minutes, "status": row.status},
        reason=comment,
    )


def _exit(req, user, comment, approved):
    from exits.models import ExitCase
    from exits.services import start_clearance

    case = ExitCase.objects.filter(pk=req.target_id).first()
    if case is None:
        return
    if not approved:
        if case.status == ExitCase.STATUS_INITIATED:
            case.status = ExitCase.STATUS_CANCELLED
            case.save(update_fields=["status", "updated_at"])
        return
    if case.status == ExitCase.STATUS_INITIATED:
        start_clearance(case, user)
    write_audit(
        organization=req.organization,
        actor=user,
        action="exit.approved",
        model="ExitCase",
        object_id=case.id,
        reason=comment,
    )
