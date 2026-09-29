from django.contrib import admin

from organizations.models import Branch, Invite, Membership, Organization, PlatformConfig, Shift, ShiftAssignment


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "org_type",
        "plan",
        "billing_exempt",
        "subscription_status",
        "is_active",
        "trial_ends_at",
        "effective_plan_display",
    )
    list_filter = ("org_type", "plan", "billing_exempt", "subscription_status", "is_active", "created_via")
    search_fields = ("name", "slug", "stripe_customer_id")
    readonly_fields = ("api_key", "slug", "created_at", "updated_at")

    @admin.display(description="Effective plan")
    def effective_plan_display(self, obj):
        return obj.effective_plan()


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "organization__name")


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "accepted_at", "expires_at")
    list_filter = ("role",)
    search_fields = ("email", "organization__name")


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "trial_days", "updated_at")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "branch", "kind", "start_time", "late_after", "end_time", "is_default", "is_active")
    list_filter = ("organization", "kind", "is_default", "is_active")
    search_fields = ("name", "organization__name")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "timezone", "is_default", "is_active")
    list_filter = ("organization", "is_default", "is_active")
    search_fields = ("name", "code", "organization__name")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "shift", "start_date", "end_date")
    list_filter = ("shift",)
    search_fields = ("employee__employee_id", "shift__name")
