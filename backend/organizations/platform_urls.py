from django.urls import path

from organizations.platform_views import (
    PlatformDashboardView,
    PlatformOrganizationDetailView,
    PlatformOrganizationListView,
    PlatformPlansView,
    PlatformSettingsView,
)

urlpatterns = [
    path("dashboard/", PlatformDashboardView.as_view(), name="platform-dashboard"),
    path("plans/", PlatformPlansView.as_view(), name="platform-plans"),
    path("settings/", PlatformSettingsView.as_view(), name="platform-settings"),
    path("organizations/", PlatformOrganizationListView.as_view(), name="platform-orgs"),
    path("organizations/<int:pk>/", PlatformOrganizationDetailView.as_view(), name="platform-org-detail"),
]
