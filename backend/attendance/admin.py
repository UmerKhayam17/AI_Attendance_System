from django.contrib import admin
from attendance.models import AttendanceCorrection, AttendanceRecord, Holiday, LeaveRequest, LeaveType, OvertimeRequest


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "date",
        "check_in",
        "check_out",
        "status",
        "early_leave",
        "missing_checkout",
        "overtime_minutes",
        "source",
    )
    list_filter = ("date", "status", "source", "early_leave", "missing_checkout")
    search_fields = (
        "employee__employee_id",
        "employee__first_name",
        "employee__last_name",
    )
    date_hierarchy = "date"


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "branch", "date", "repeats_yearly")
    list_filter = ("organization", "branch", "repeats_yearly")
    search_fields = ("name",)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")
    search_fields = ("employee__employee_id", "employee__first_name")


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("organization", "code", "name", "entitlement_days", "paid", "is_active")


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status")


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "minutes", "status")

