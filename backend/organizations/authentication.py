from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from organizations.models import Membership, Organization


def attach_membership(request, user):
    if user.is_superuser:
        request.organization = None
        request.membership = None
        request.role = "superadmin"
        request.is_platform_admin = True
        return None
    membership = (
        Membership.objects.select_related("organization")
        .filter(user=user)
        .first()
    )
    if not membership:
        raise AuthenticationFailed("No organization membership")
    if not membership.organization.is_active:
        raise AuthenticationFailed("Organization is suspended")
    request.organization = membership.organization
    request.membership = membership
    request.role = membership.role
    request.is_platform_admin = False
    return membership


class TenantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        attach_membership(request, user)
        return user, token


class OrganizationApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = (
            request.headers.get("X-API-Key")
            or request.META.get("HTTP_X_API_KEY", "")
        ).strip()
        if not key:
            return None

        org = Organization.objects.filter(api_key=key, is_active=True).first()
        if not org:
            raise AuthenticationFailed("Invalid API key")
        if not org.has_feature("api_key"):
            raise AuthenticationFailed("API key access requires the Pro plan")

        owner = (
            Membership.objects.filter(
                organization=org,
                role=Membership.ROLE_OWNER,
            )
            .select_related("user")
            .first()
        )
        if not owner:
            raise AuthenticationFailed("Organization has no owner")

        request.organization = org
        request.membership = None
        request.role = "api"
        return owner.user, None
