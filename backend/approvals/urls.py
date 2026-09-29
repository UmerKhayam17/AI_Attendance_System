from django.urls import path

from approvals.views import (
    ApprovalDecideView,
    AuditListView,
    InboxView,
    NotificationListView,
    NotificationReadView,
    WorkflowDetailView,
    WorkflowListView,
)

urlpatterns = [
    path("workflows/", WorkflowListView.as_view(), name="approval-workflows"),
    path("workflows/<int:pk>/", WorkflowDetailView.as_view(), name="approval-workflow-detail"),
    path("inbox/", InboxView.as_view(), name="approval-inbox"),
    path("requests/<int:pk>/approve/", ApprovalDecideView.as_view(), {"action": "approve"}, name="approval-approve"),
    path("requests/<int:pk>/reject/", ApprovalDecideView.as_view(), {"action": "reject"}, name="approval-reject"),
    path("notifications/", NotificationListView.as_view(), name="approval-notifications"),
    path("notifications/read/", NotificationReadView.as_view(), name="approval-notifications-read-all"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="approval-notification-read"),
    path("audit/", AuditListView.as_view(), name="approval-audit"),
]
