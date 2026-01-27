from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "source_name",
        "full_name",
        "email",
        "phone_e164",
        "event_date",
        "created_at",
    )
    list_filter = ("status", "source_name", "country_code")
    search_fields = ("full_name", "email", "phone_e164", "source_ref")
    readonly_fields = ("created_at", "updated_at", "raw_payload_hash")
