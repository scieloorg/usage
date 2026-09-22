from django.contrib import admin

from counter_api.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "active",
        "expires_at",
        "last_used_at",
        "created_at",
    )
    list_filter = ("active",)
    search_fields = ("name",)
    fields = ("name", "active", "expires_at", "last_used_at", "created_at")
    readonly_fields = ("name", "last_used_at", "created_at")

    def has_add_permission(self, request):
        return False
