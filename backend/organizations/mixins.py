from rest_framework.exceptions import PermissionDenied


class OrganizationScopedMixin:
    organization_field = "organization"

    def get_organization(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            raise PermissionDenied("No organization in session")
        return org

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org is None:
            return qs.none()
        return qs.filter(**{self.organization_field: org})
