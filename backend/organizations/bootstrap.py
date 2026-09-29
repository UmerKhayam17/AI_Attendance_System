import logging

from django.conf import settings
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def ensure_superadmin() -> User | None:
    email = (getattr(settings, "SUPERADMIN_EMAIL", "") or "").strip().lower()
    password = getattr(settings, "SUPERADMIN_PASSWORD", "") or ""
    if not email or not password:
        logger.warning("SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD not set; skipping bootstrap")
        return None

    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": "Super",
            "last_name": "Admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    changed = False
    if created:
        user.set_password(password)
        changed = True
        logger.info("Created platform super admin %s", email)
    else:
        if not user.is_superuser or not user.is_staff or not user.is_active:
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            changed = True
        if user.email != email:
            user.email = email
            changed = True
    if changed:
        user.save()
    return user
