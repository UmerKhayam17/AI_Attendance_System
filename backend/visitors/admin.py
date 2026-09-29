from django.contrib import admin

from visitors.models import Visit, Visitor


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "company", "organization", "is_blacklisted")
    list_filter = ("is_blacklisted", "organization")
    search_fields = ("first_name", "last_name", "phone", "company", "id_number")


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("visitor", "host", "status", "purpose", "expected_at", "badge_code", "organization")
    list_filter = ("status", "purpose", "source", "organization")
    search_fields = ("visitor__first_name", "badge_code", "public_token")
