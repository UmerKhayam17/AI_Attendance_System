from django.urls import path

from employees.portal_views import (
    PortalBalanceView,
    PortalCorrectionView,
    PortalDocumentView,
    PortalLeaveView,
    PortalOvertimeView,
    PortalPayslipView,
    PortalPunchView,
    PortalResignationView,
    PortalStatusView,
)

urlpatterns = [
    path("status/", PortalStatusView.as_view(), name="portal-status"),
    path("punch/", PortalPunchView.as_view(), name="portal-punch"),
    path("leave/", PortalLeaveView.as_view(), name="portal-leave"),
    path("balances/", PortalBalanceView.as_view(), name="portal-balances"),
    path("corrections/", PortalCorrectionView.as_view(), name="portal-corrections"),
    path("overtime/", PortalOvertimeView.as_view(), name="portal-overtime"),
    path("documents/", PortalDocumentView.as_view(), name="portal-documents"),
    path("payslips/", PortalPayslipView.as_view(), name="portal-payslips"),
    path("resignation/", PortalResignationView.as_view(), name="portal-resignation"),
]
