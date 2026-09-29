from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from exits.models import (
    ExitCase,
    ExitChecklistTemplate,
    ExitClearanceItem,
    ExitPolicy,
    notice_days_for,
    seed_checklist_templates,
    suggested_last_working_day,
)


def init_exit_module(organization) -> ExitPolicy:
    policy = ExitPolicy.for_org(organization)
    seed_checklist_templates(organization)
    return policy


@transaction.atomic
def initiate_exit(*, organization, employee, user, data: dict) -> ExitCase:
    if ExitCase.objects.filter(
        employee=employee,
        status__in=[ExitCase.STATUS_INITIATED, ExitCase.STATUS_IN_PROGRESS],
    ).exists():
        raise ValidationError({"error": "This person already has an open exit case"})

    policy = init_exit_module(organization)
    resignation = data.get("resignation_date") or date.today()
    if isinstance(resignation, str):
        resignation = date.fromisoformat(resignation)
    notice = data.get("notice_period_days")
    if notice is None:
        notice = notice_days_for(policy, employee, resignation)
    last_day = data.get("last_working_day")
    if last_day is None:
        last_day = resignation + timedelta(days=int(notice))
    elif isinstance(last_day, str):
        last_day = date.fromisoformat(last_day)

    case = ExitCase.objects.create(
        organization=organization,
        employee=employee,
        exit_type=data.get("exit_type") or ExitCase.TYPE_RESIGNATION,
        status=ExitCase.STATUS_IN_PROGRESS,
        resignation_date=resignation,
        last_working_day=last_day,
        notice_period_days=int(notice),
        notice_buyout_days=int(data.get("notice_buyout_days") or 0),
        reason=data.get("reason") or "",
        handover_notes=data.get("handover_notes") or "",
        initiated_by=user,
    )
    templates = ExitChecklistTemplate.objects.filter(organization=organization, is_active=True)
    ExitClearanceItem.objects.bulk_create(
        [
            ExitClearanceItem(
                case=case,
                category=row.category,
                title=row.title,
                sort_order=row.sort_order,
            )
            for row in templates
        ]
    )
    return case


def start_clearance(case: ExitCase, user=None) -> ExitCase:
    if case.status == ExitCase.STATUS_COMPLETED:
        raise ValidationError({"error": "Exit is already completed"})
    if case.status == ExitCase.STATUS_CANCELLED:
        raise ValidationError({"error": "Cancelled exits cannot be started"})
    init_exit_module(case.organization)
    if not case.checklist_items.exists():
        templates = ExitChecklistTemplate.objects.filter(organization=case.organization, is_active=True)
        ExitClearanceItem.objects.bulk_create(
            [
                ExitClearanceItem(
                    case=case,
                    category=row.category,
                    title=row.title,
                    sort_order=row.sort_order,
                )
                for row in templates
            ]
        )
    case.status = ExitCase.STATUS_IN_PROGRESS
    case.save(update_fields=["status", "updated_at"])
    return case


def request_resignation(*, organization, employee, user, data: dict) -> ExitCase:
    if ExitCase.objects.filter(
        employee=employee,
        status__in=[ExitCase.STATUS_INITIATED, ExitCase.STATUS_IN_PROGRESS],
    ).exists():
        raise ValidationError({"error": "This person already has an open exit case"})
    policy = init_exit_module(organization)
    resignation = data.get("resignation_date") or date.today()
    if isinstance(resignation, str):
        resignation = date.fromisoformat(resignation)
    notice = data.get("notice_period_days")
    if notice is None:
        notice = notice_days_for(policy, employee, resignation)
    last_day = data.get("last_working_day")
    if last_day is None:
        last_day = resignation + timedelta(days=int(notice))
    elif isinstance(last_day, str):
        last_day = date.fromisoformat(last_day)
    case = ExitCase.objects.create(
        organization=organization,
        employee=employee,
        exit_type=ExitCase.TYPE_RESIGNATION,
        status=ExitCase.STATUS_INITIATED,
        resignation_date=resignation,
        last_working_day=last_day,
        notice_period_days=int(notice),
        reason=data.get("reason") or "",
        handover_notes=data.get("handover_notes") or "",
        initiated_by=user,
    )
    from approvals.engine import submit
    from approvals.models import ApprovalWorkflow

    submit(
        organization=organization,
        kind=ApprovalWorkflow.KIND_EXIT,
        target_id=case.pk,
        employee=employee,
        user=user,
    )
    return case


def complete_exit(case: ExitCase, user) -> ExitCase:
    policy = ExitPolicy.for_org(case.organization)
    if case.status == ExitCase.STATUS_COMPLETED:
        raise ValidationError({"error": "Exit is already completed"})
    if case.status == ExitCase.STATUS_CANCELLED:
        raise ValidationError({"error": "Cancelled exits cannot be completed"})
    if policy.require_clearance and not case.clearance_done:
        raise ValidationError({"error": "Clear all checklist items before completing"})
    if policy.require_interview and not case.interview_completed:
        raise ValidationError({"error": "Mark the exit interview complete first"})
    if policy.allow_notice_buyout is False and case.notice_buyout_days:
        raise ValidationError({"error": "Notice buyout is not allowed by policy"})

    case.status = ExitCase.STATUS_COMPLETED
    case.completed_at = timezone.now()
    case.save(update_fields=["status", "completed_at", "updated_at"])

    if policy.auto_deactivate:
        employee = case.employee
        if employee.is_active:
            employee.is_active = False
            employee.save(update_fields=["is_active", "updated_at"])
        try:
            from recognition.services.gallery_index import invalidate_gallery

            invalidate_gallery(employee.organization_id)
        except Exception:
            pass
    try:
        from approvals.audit import write_audit

        write_audit(
            organization=case.organization,
            actor=user,
            action="exit.complete",
            model="ExitCase",
            object_id=case.id,
            new_value={"employee_id": case.employee.employee_id, "status": case.status},
        )
    except Exception:
        pass
    return case
