from django.contrib import admin

from approvals.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStep,
    ApprovalWorkflow,
    AuditEvent,
    InAppNotification,
)


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ("organization", "kind", "is_active")
    list_filter = ("kind", "is_active")
    inlines = [ApprovalStepInline]


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("kind", "employee", "status", "created_at")
    list_filter = ("kind", "status")


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("request", "action", "actor", "created_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("organization", "action", "model", "actor", "created_at")
    list_filter = ("action", "model")


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "read_at", "created_at")
