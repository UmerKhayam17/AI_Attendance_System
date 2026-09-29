from django.urls import path

from organizations.views import (
    BranchDetailView,
    BranchListView,
    DepartmentDetailView,
    DepartmentListView,
    IntegrationsView,
    InviteListView,
    InviteRevokeView,
    MemberDetailView,
    MemberListView,
    MeView,
    OrganizationDetailView,
    RotateApiKeyView,
    ShiftDetailView,
    ShiftListView,
)
from attendance.views import LeaveTypeDetailView, LeaveTypeListView

urlpatterns = [
    path("me/", MeView.as_view(), name="org-me"),
    path("", OrganizationDetailView.as_view(), name="org-detail"),
    path("members/", MemberListView.as_view(), name="org-members"),
    path("members/<int:pk>/", MemberDetailView.as_view(), name="org-member-detail"),
    path("invites/", InviteListView.as_view(), name="org-invites"),
    path("invites/<int:pk>/", InviteRevokeView.as_view(), name="org-invite-revoke"),
    path("integrations/", IntegrationsView.as_view(), name="org-integrations"),
    path("integrations/rotate-key/", RotateApiKeyView.as_view(), name="org-rotate-key"),
    path("branches/", BranchListView.as_view(), name="org-branches"),
    path("branches/<int:pk>/", BranchDetailView.as_view(), name="org-branch-detail"),
    path("shifts/", ShiftListView.as_view(), name="org-shifts"),
    path("shifts/<int:pk>/", ShiftDetailView.as_view(), name="org-shift-detail"),
    path("departments/", DepartmentListView.as_view(), name="org-departments"),
    path("departments/<int:pk>/", DepartmentDetailView.as_view(), name="org-department-detail"),
    path("leave-types/", LeaveTypeListView.as_view(), name="org-leave-types"),
    path("leave-types/<int:pk>/", LeaveTypeDetailView.as_view(), name="org-leave-type-detail"),
]
