from django.urls import include, path
from rest_framework.routers import DefaultRouter

from attendance.views import (
    AttendanceCorrectionViewSet,
    AttendanceViewSet,
    HolidayViewSet,
    LeaveRequestViewSet,
    LeaveTypeDetailView,
    LeaveTypeListView,
    ManualAttendanceView,
    OvertimeRequestViewSet,
)

router = DefaultRouter()
router.register("records", AttendanceViewSet, basename="attendance-record")
router.register("holidays", HolidayViewSet, basename="holiday")
router.register("leave", LeaveRequestViewSet, basename="leave-request")
router.register("corrections", AttendanceCorrectionViewSet, basename="attendance-correction")
router.register("overtime", OvertimeRequestViewSet, basename="overtime-request")

urlpatterns = [
    path("manual/", ManualAttendanceView.as_view(), name="manual-attendance"),
    path("leave-types/", LeaveTypeListView.as_view(), name="leave-types"),
    path("leave-types/<int:pk>/", LeaveTypeDetailView.as_view(), name="leave-type-detail"),
    path("", include(router.urls)),
]
