from attendance.models import OvertimeRequest
from payroll.models import PayrollPolicy


def maybe_suggest_overtime(record, employee):
    minutes = int(record.overtime_minutes or 0)
    if minutes <= 0:
        return None
    org = employee.organization
    policy = PayrollPolicy.for_org(org)
    if not policy.overtime_requires_approval:
        return None
    existing = OvertimeRequest.objects.filter(
        employee=employee,
        date=record.date,
        status__in=[OvertimeRequest.STATUS_PENDING, OvertimeRequest.STATUS_APPROVED],
    ).first()
    if existing:
        if existing.status == OvertimeRequest.STATUS_PENDING and existing.minutes < minutes:
            existing.minutes = minutes
            existing.save(update_fields=["minutes", "updated_at"])
        return existing
    row = OvertimeRequest.objects.create(
        employee=employee,
        date=record.date,
        minutes=minutes,
        source=OvertimeRequest.SOURCE_AUTO,
        reason="Recorded overtime pending approval",
    )
    try:
        from approvals.engine import submit
        from approvals.models import ApprovalWorkflow

        submit(
            organization=org,
            kind=ApprovalWorkflow.KIND_OVERTIME,
            target_id=row.pk,
            employee=employee,
            user=getattr(employee, "user", None),
        )
    except Exception:
        pass
    return row
