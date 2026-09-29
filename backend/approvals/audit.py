from approvals.models import AuditEvent


def write_audit(
    *,
    organization,
    actor=None,
    action: str,
    model: str,
    object_id="",
    old_value=None,
    new_value=None,
    reason="",
    request=None,
):
    if organization is None:
        return None
    ip = None
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    return AuditEvent.objects.create(
        organization=organization,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        model=model,
        object_id=str(object_id or ""),
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason or "",
        ip_address=ip or None,
    )
