from rest_framework_simplejwt.tokens import RefreshToken

from organizations.models import Membership


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    membership = (
        Membership.objects.select_related("organization").filter(user=user).first()
    )
    if user.is_superuser:
        refresh["role"] = "superadmin"
        refresh.access_token["role"] = "superadmin"
    elif membership:
        refresh["org_id"] = membership.organization_id
        refresh["role"] = membership.role
        refresh.access_token["org_id"] = membership.organization_id
        refresh.access_token["role"] = membership.role
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
