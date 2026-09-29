"""In-app notifications plus optional email for HR events."""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail

from approvals.models import InAppNotification
from organizations.models import Membership

logger = logging.getLogger(__name__)


def staff_users(organization):
    return list(
        User.objects.filter(
            memberships__organization=organization,
            memberships__role__in=[Membership.ROLE_OWNER, Membership.ROLE_ADMIN],
            is_active=True,
        ).distinct()
    )


def notify_users(organization, users, *, kind, title, body="", link=""):
    seen = set()
    for user in users:
        if user is None or user.id in seen:
            continue
        seen.add(user.id)
        InAppNotification.objects.create(
            organization=organization,
            user=user,
            kind=kind,
            title=title,
            body=body,
            link=link,
        )


def email_user(user, subject: str, message: str, organization=None):
    if organization is not None and not getattr(organization, "notify_email", True):
        return
    to = (getattr(user, "email", None) or getattr(user, "username", "") or "").strip()
    if "@" not in to:
        return
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
            recipient_list=[to],
            fail_silently=True,
        )
    except Exception:
        logger.exception("HR email failed")


def notify_async(fn, *args, **kwargs):
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True, name="hr-notify").start()
