from django.urls import path

from payroll.views import (
    CompensationListView,
    CompensationView,
    LeaveBalanceView,
    PayrollDefaultPeriodView,
    PayrollPolicyView,
    PayrollRunDetailView,
    PayrollRunFinalizeView,
    PayrollRunListView,
)

urlpatterns = [
    path("policy/", PayrollPolicyView.as_view(), name="payroll-policy"),
    path("period-default/", PayrollDefaultPeriodView.as_view(), name="payroll-period-default"),
    path("leave-balances/", LeaveBalanceView.as_view(), name="payroll-leave-balances"),
    path("compensation/", CompensationListView.as_view(), name="payroll-compensation-list"),
    path("compensation/<str:employee_id>/", CompensationView.as_view(), name="payroll-compensation"),
    path("runs/", PayrollRunListView.as_view(), name="payroll-runs"),
    path("runs/<int:pk>/", PayrollRunDetailView.as_view(), name="payroll-run-detail"),
    path("runs/<int:pk>/finalize/", PayrollRunFinalizeView.as_view(), name="payroll-run-finalize"),
]
