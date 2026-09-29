from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from approvals.audit import write_audit
from approvals.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStep,
    ApprovalWorkflow,
)
from approvals.notify import email_user, notify_users, staff_users
from organizations.models import Membership


def workflow_for(organization, kind: str) -> ApprovalWorkflow:
    from approvals.bootstrap import seed_workflows

    seed_workflows(organization)
    workflow = ApprovalWorkflow.objects.filter(
        organization=organization, kind=kind, is_active=True
    ).first()
    if workflow is None:
        raise ValidationError({"error": "No approval workflow is configured for this request"})
    return workflow


def steps_for(employee, workflow: ApprovalWorkflow) -> list[ApprovalStep]:
    steps = list(workflow.steps.order_by("order", "id"))
    usable = []
    for step in steps:
        if step.assignee_role == ApprovalStep.ROLE_MANAGER and not getattr(employee, "manager_id", None):
            continue
        usable.append(step)
    if not usable:
        fallback = next((s for s in steps if s.assignee_role == ApprovalStep.ROLE_ADMIN), None)
        if fallback:
            usable = [fallback]
    return usable


def membership_role(user, organization) -> str | None:
    if user is None:
        return None
    row = Membership.objects.filter(user=user, organization=organization).first()
    return row.role if row else None


def can_act(user, request: ApprovalRequest, step: ApprovalStep | None = None) -> bool:
    if user is None or not user.is_authenticated:
        return False
    org = request.organization
    role = membership_role(user, org)
    if role == Membership.ROLE_OWNER:
        return True
    step = step or request.current_step
    if step is None:
        return role in (Membership.ROLE_OWNER, Membership.ROLE_ADMIN)
    if step.assignee_role == ApprovalStep.ROLE_OWNER:
        return role == Membership.ROLE_OWNER
    if step.assignee_role == ApprovalStep.ROLE_ADMIN:
        return role in (Membership.ROLE_OWNER, Membership.ROLE_ADMIN)
    if step.assignee_role == ApprovalStep.ROLE_MANAGER:
        manager = getattr(request.employee, "manager", None)
        if manager and manager.user_id == user.id:
            return True
        return role in (Membership.ROLE_OWNER, Membership.ROLE_ADMIN)
    return False


def pending_for(organization, kind: str, target_id: int) -> ApprovalRequest | None:
    return (
        ApprovalRequest.objects.filter(
            organization=organization,
            kind=kind,
            target_id=target_id,
            status=ApprovalRequest.STATUS_PENDING,
        )
        .select_related("current_step", "employee", "employee__manager", "employee__user")
        .first()
    )


def submit(*, organization, kind: str, target_id: int, employee, user) -> ApprovalRequest:
    existing = pending_for(organization, kind, target_id)
    if existing:
        return existing
    workflow = workflow_for(organization, kind)
    steps = steps_for(employee, workflow)
    first = steps[0] if steps else None
    req = ApprovalRequest.objects.create(
        organization=organization,
        kind=kind,
        target_id=target_id,
        employee=employee,
        submitted_by=user if getattr(user, "is_authenticated", False) else None,
        current_step=first,
        status=ApprovalRequest.STATUS_PENDING,
    )
    _notify_assignees(req)
    return req


def inbox_for(user, organization):
    rows = (
        ApprovalRequest.objects.filter(organization=organization, status=ApprovalRequest.STATUS_PENDING)
        .select_related("current_step", "employee", "employee__manager", "employee__user", "submitted_by")
        .order_by("created_at")
    )
    return [row for row in rows if can_act(user, row, row.current_step)]


def approve(req: ApprovalRequest, user, comment: str = "") -> ApprovalRequest:
    return _decide(req, user, ApprovalAction.ACTION_APPROVE, comment)


def reject(req: ApprovalRequest, user, comment: str = "") -> ApprovalRequest:
    return _decide(req, user, ApprovalAction.ACTION_REJECT, comment)


@transaction.atomic
def _decide(req: ApprovalRequest, user, action: str, comment: str) -> ApprovalRequest:
    if req.status != ApprovalRequest.STATUS_PENDING:
        raise ValidationError({"error": "This request is no longer pending"})
    if not can_act(user, req, req.current_step):
        raise PermissionDenied("You cannot act on this approval")
    ApprovalAction.objects.create(
        request=req,
        step=req.current_step,
        actor=user,
        action=action,
        comment=comment or "",
    )
    if action == ApprovalAction.ACTION_REJECT:
        from approvals.handlers import on_final

        on_final(req, user, comment, approved=False)
        req.status = ApprovalRequest.STATUS_REJECTED
        req.current_step = None
        req.decided_at = timezone.now()
        req.save(update_fields=["status", "current_step", "decided_at", "updated_at"])
        _notify_decision(req, approved=False)
        return req

    workflow = req.current_step.workflow if req.current_step_id else workflow_for(req.organization, req.kind)
    remaining = [
        step
        for step in steps_for(req.employee, workflow)
        if req.current_step_id is None
        or step.order > req.current_step.order
        or (step.order == req.current_step.order and step.id > req.current_step_id)
    ]
    next_step = remaining[0] if remaining else None
    if next_step:
        req.current_step = next_step
        req.save(update_fields=["current_step", "updated_at"])
        _notify_assignees(req)
        return req

    from approvals.handlers import on_final

    on_final(req, user, comment, approved=True)
    req.status = ApprovalRequest.STATUS_APPROVED
    req.current_step = None
    req.decided_at = timezone.now()
    req.save(update_fields=["status", "current_step", "decided_at", "updated_at"])
    _notify_decision(req, approved=True)
    return req


def _notify_assignees(req: ApprovalRequest):
    step = req.current_step
    users = []
    if step is None or step.assignee_role in (ApprovalStep.ROLE_ADMIN, ApprovalStep.ROLE_OWNER):
        users = staff_users(req.organization)
        if step and step.assignee_role == ApprovalStep.ROLE_OWNER:
            users = [
                u
                for u in users
                if Membership.objects.filter(
                    user=u, organization=req.organization, role=Membership.ROLE_OWNER
                ).exists()
            ]
    elif step.assignee_role == ApprovalStep.ROLE_MANAGER:
        manager = getattr(req.employee, "manager", None)
        if manager and manager.user_id:
            users = [manager.user]
        users.extend(staff_users(req.organization))
    name = req.employee.display_name
    title = f"{req.get_kind_display()} waiting for you"
    body = f"{name} submitted a {req.get_kind_display().lower()} request."
    link = "/leave" if req.kind == ApprovalWorkflow.KIND_LEAVE else "/me"
    notify_users(req.organization, users, kind="approval", title=title, body=body, link=link)


def _notify_decision(req: ApprovalRequest, *, approved: bool):
    users = []
    if req.submitted_by_id:
        users.append(req.submitted_by)
    if req.employee.user_id:
        users.append(req.employee.user)
    verb = "approved" if approved else "rejected"
    title = f"{req.get_kind_display()} {verb}"
    body = f"Your {req.get_kind_display().lower()} request was {verb}."
    kind = {
        ApprovalWorkflow.KIND_LEAVE: "leave",
        ApprovalWorkflow.KIND_CORRECTION: "correction",
        ApprovalWorkflow.KIND_OVERTIME: "overtime",
        ApprovalWorkflow.KIND_EXIT: "exit",
    }.get(req.kind, "approval")
    notify_users(req.organization, users, kind=kind, title=title, body=body, link="/me")
    for user in users:
        email_user(user, title, body, organization=req.organization)
    write_audit(
        organization=req.organization,
        actor=req.actions.order_by("-id").first().actor if req.actions.exists() else None,
        action=f"{req.kind}.{verb}",
        model="ApprovalRequest",
        object_id=req.id,
        new_value={"kind": req.kind, "target_id": req.target_id, "status": req.status},
    )
