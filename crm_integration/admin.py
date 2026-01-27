from django.contrib import admin

from .models import PerfexLeadSync


@admin.register(PerfexLeadSync)
class PerfexLeadSyncAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lead",
        "status",
        "perfex_lead_id",
        "last_sync_at",
        "attempts",
        "next_retry_at",
    )
    list_filter = ("status",)
    search_fields = ("lead__full_name", "lead__email", "perfex_lead_id", "last_error")
    readonly_fields = ("created_at", "updated_at", "payload_hash")
