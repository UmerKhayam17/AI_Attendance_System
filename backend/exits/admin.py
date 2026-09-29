from django.contrib import admin

from exits.models import ExitCase, ExitChecklistTemplate, ExitClearanceItem, ExitPolicy


@admin.register(ExitPolicy)
class ExitPolicyAdmin(admin.ModelAdmin):
    list_display = ("organization", "notice_period_days", "require_clearance", "auto_deactivate")


@admin.register(ExitChecklistTemplate)
class ExitChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "category", "is_active", "sort_order")
    list_filter = ("organization", "category", "is_active")


class ExitClearanceInline(admin.TabularInline):
    model = ExitClearanceItem
    extra = 0


@admin.register(ExitCase)
class ExitCaseAdmin(admin.ModelAdmin):
    list_display = ("employee", "exit_type", "status", "last_working_day", "organization")
    list_filter = ("status", "exit_type", "organization")
    inlines = [ExitClearanceInline]
