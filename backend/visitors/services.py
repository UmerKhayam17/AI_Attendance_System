from django.utils import timezone
from rest_framework.exceptions import ValidationError

from organizations.localtime import local_now
from visitors.models import Visit, Visitor


def find_or_create_visitor(organization, data: dict) -> Visitor:
    first = (data.get("first_name") or "").strip()
    if not first:
        raise ValidationError({"first_name": "Visitor first name is required"})
    phone = (data.get("phone") or "").strip()
    id_number = (data.get("id_number") or "").strip()
    qs = Visitor.objects.filter(organization=organization)
    visitor = None
    if phone:
        visitor = qs.filter(phone=phone).first()
    if visitor is None and id_number:
        visitor = qs.filter(id_number=id_number).exclude(id_number="").first()
    payload = {
        "first_name": first,
        "last_name": (data.get("last_name") or "").strip(),
        "phone": phone,
        "email": (data.get("email") or "").strip(),
        "company": (data.get("company") or "").strip(),
        "id_type": data.get("id_type") or Visitor.ID_CNIC,
        "id_number": id_number,
        "notes": (data.get("notes") or "").strip(),
    }
    if visitor is None:
        return Visitor.objects.create(organization=organization, **payload)
    for key, value in payload.items():
        if value:
            setattr(visitor, key, value)
    visitor.save()
    return visitor


def next_badge(organization) -> str:
    today = local_now(organization=organization).strftime("%y%m%d")
    prefix = f"V{today}"
    last = (
        Visit.objects.filter(organization=organization, badge_code__startswith=prefix)
        .order_by("-badge_code")
        .values_list("badge_code", flat=True)
        .first()
    )
    seq = 1
    if last and last[len(prefix) :].isdigit():
        seq = int(last[len(prefix) :]) + 1
    return f"{prefix}{seq:03d}"


def create_visit(organization, data: dict, *, user=None) -> Visit:
    visitor = data.get("visitor")
    if visitor is None:
        visitor = find_or_create_visitor(organization, data)
    if visitor.is_blacklisted:
        raise ValidationError({"visitor": f"{visitor.full_name} is on the watchlist"})
    visit = Visit.objects.create(
        organization=organization,
        visitor=visitor,
        host=data.get("host"),
        branch=data.get("branch") or organization.default_branch(),
        purpose=data.get("purpose") or Visit.PURPOSE_MEETING,
        source=data.get("source") or Visit.SOURCE_WALKIN,
        expected_at=data.get("expected_at") or timezone.now(),
        expected_end=data.get("expected_end"),
        vehicle_plate=(data.get("vehicle_plate") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        created_by=user,
    )
    return visit


def check_in(visit: Visit) -> Visit:
    if visit.visitor.is_blacklisted:
        raise ValidationError({"visitor": f"{visit.visitor.full_name} is on the watchlist and cannot enter"})
    if visit.status == Visit.STATUS_CHECKED_IN:
        raise ValidationError({"status": "Visitor is already on site"})
    if visit.status in (Visit.STATUS_CANCELLED, Visit.STATUS_DENIED, Visit.STATUS_CHECKED_OUT):
        raise ValidationError({"status": f"Cannot check in a {visit.get_status_display().lower()} visit"})
    visit.status = Visit.STATUS_CHECKED_IN
    visit.check_in_at = timezone.now()
    if not visit.badge_code:
        visit.badge_code = next_badge(visit.organization)
    visit.save(update_fields=["status", "check_in_at", "badge_code", "updated_at"])
    _notify_host(visit, arrived=True)
    return visit


def check_out(visit: Visit) -> Visit:
    if visit.status != Visit.STATUS_CHECKED_IN:
        raise ValidationError({"status": "Visitor is not currently on site"})
    visit.status = Visit.STATUS_CHECKED_OUT
    visit.check_out_at = timezone.now()
    visit.save(update_fields=["status", "check_out_at", "updated_at"])
    return visit


def cancel_visit(visit: Visit) -> Visit:
    if visit.status == Visit.STATUS_CHECKED_IN:
        raise ValidationError({"status": "Check the visitor out before cancelling"})
    if visit.status not in (Visit.STATUS_EXPECTED,):
        raise ValidationError({"status": "Only expected visits can be cancelled"})
    visit.status = Visit.STATUS_CANCELLED
    visit.save(update_fields=["status", "updated_at"])
    return visit


def mark_no_show(visit: Visit) -> Visit:
    if visit.status != Visit.STATUS_EXPECTED:
        raise ValidationError({"status": "Only expected visits can be marked no-show"})
    visit.status = Visit.STATUS_NO_SHOW
    visit.save(update_fields=["status", "updated_at"])
    return visit


def deny_visit(visit: Visit, reason: str = "") -> Visit:
    if visit.status == Visit.STATUS_CHECKED_IN:
        visit.check_out_at = timezone.now()
    visit.status = Visit.STATUS_DENIED
    visit.denied_reason = (reason or "")[:240]
    visit.save(update_fields=["status", "denied_reason", "check_out_at", "updated_at"])
    return visit


def set_watchlist(visitor: Visitor, blocked: bool, reason: str = "") -> Visitor:
    visitor.is_blacklisted = blocked
    visitor.blacklist_reason = (reason or "")[:240] if blocked else ""
    visitor.save(update_fields=["is_blacklisted", "blacklist_reason", "updated_at"])
    return visitor


def _notify_host(visit: Visit, *, arrived: bool):
    host = visit.host
    user = getattr(host, "user", None) if host else None
    if user is None:
        return
    name = visit.visitor.full_name
    title = f"{name} has arrived" if arrived else f"Visit update: {name}"
    body = f"{name} checked in"
    if visit.badge_code:
        body += f" · badge {visit.badge_code}"
    try:
        from approvals.notify import notify_async, notify_users, email_user

        def _send():
            try:
                notify_users(
                    visit.organization,
                    [user],
                    kind="visitor",
                    title=title,
                    body=body,
                    link="/visitors",
                )
                email_user(user, title, body, organization=visit.organization)
            except Exception:
                pass

        notify_async(_send)
    except Exception:
        pass
