from django.urls import path

from dashboard.views import DailyReportView, DashboardSummaryView, ExportReportView, HrReportView, RangeReportView, RecognitionReportView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("daily-report/", DailyReportView.as_view(), name="daily-report"),
    path("range-report/", RangeReportView.as_view(), name="range-report"),
    path("hr-report/", HrReportView.as_view(), name="hr-report"),
    path("recognition-report/", RecognitionReportView.as_view(), name="recognition-report"),
    path("export/", ExportReportView.as_view(), name="report-export"),
]
