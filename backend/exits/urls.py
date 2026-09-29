from django.urls import path

from exits.views import (
    ExitCaseCancelView,
    ExitCaseCompleteView,
    ExitCaseDetailView,
    ExitCaseListView,
    ExitChecklistTemplateDetailView,
    ExitChecklistTemplateListView,
    ExitClearanceToggleView,
    ExitPolicyView,
    ExitSuggestView,
)

urlpatterns = [
    path("policy/", ExitPolicyView.as_view(), name="exit-policy"),
    path("checklist/", ExitChecklistTemplateListView.as_view(), name="exit-checklist"),
    path("checklist/<int:pk>/", ExitChecklistTemplateDetailView.as_view(), name="exit-checklist-detail"),
    path("suggest/", ExitSuggestView.as_view(), name="exit-suggest"),
    path("cases/", ExitCaseListView.as_view(), name="exit-cases"),
    path("cases/<int:pk>/", ExitCaseDetailView.as_view(), name="exit-case-detail"),
    path("cases/<int:pk>/complete/", ExitCaseCompleteView.as_view(), name="exit-case-complete"),
    path("cases/<int:pk>/cancel/", ExitCaseCancelView.as_view(), name="exit-case-cancel"),
    path("cases/<int:pk>/items/<int:item_id>/toggle/", ExitClearanceToggleView.as_view(), name="exit-item-toggle"),
]
