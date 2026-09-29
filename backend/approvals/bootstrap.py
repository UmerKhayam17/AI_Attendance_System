from approvals.models import ApprovalStep, ApprovalWorkflow


def seed_workflows(organization):
    for kind in ApprovalWorkflow.KINDS:
        workflow, created = ApprovalWorkflow.objects.get_or_create(
            organization=organization,
            kind=kind,
            defaults={"is_active": True},
        )
        if created or not workflow.steps.exists():
            ApprovalStep.objects.get_or_create(
                workflow=workflow,
                order=1,
                defaults={"assignee_role": ApprovalStep.ROLE_ADMIN},
            )
    return list(organization.approval_workflows.all())
