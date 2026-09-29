from django.contrib import admin
from .models import Department, Employee, EmployeeDocument


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "first_name",
        "last_name",
        "email",
        "organization",
        "branch",
        "department",
        "shift",
        "employment_type",
        "is_active",
    )
    list_filter = ("organization", "branch", "is_active", "employment_type", "department", "shift")
    search_fields = (
        "employee_id",
        "first_name",
        "last_name",
        "email",
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "branch", "is_active", "sort_order")
    list_filter = ("organization", "branch", "is_active")
    search_fields = ("name",)


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "employee", "category", "uploaded_at")
    list_filter = ("category",)
    search_fields = ("title", "employee__employee_id")
