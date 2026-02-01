import json

from django.contrib import admin
from django.utils.html import format_html

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
    readonly_fields = ("created_at", "updated_at", "raw_payload_hash", "raw_payload_display")
    
    fieldsets = (
        ("Contact Information", {
            "fields": ("full_name", "email", "phone_raw", "phone_e164", "company", "position", "website")
        }),
        ("Address", {
            "fields": ("address", "city", "state", "zip_code", "country_code")
        }),
        ("Event Information", {
            "fields": ("event_date", "event_datetime", "event_text")
        }),
        ("Additional", {
            "fields": ("default_language", "lead_value", "status", "notes")
        }),
        ("Source Information", {
            "fields": ("source_name", "source_url", "source_ref")
        }),
        ("Debug Information", {
            "fields": ("raw_payload_display", "raw_payload_hash"),
            "classes": ("collapse",),
            "description": "Raw extracted data for debugging. Check this if fields are blank."
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def raw_payload_display(self, obj):
        """Display raw payload in a readable format."""
        if not obj.raw_payload:
            return "No raw payload data"
        
        # Format as pretty JSON
        try:
            formatted = json.dumps(obj.raw_payload, indent=2, ensure_ascii=False)
            # Highlight empty fields
            formatted_html = formatted.replace('""', '<span style="color: red; font-weight: bold;">""</span>')
            formatted_html = formatted_html.replace('null', '<span style="color: orange;">null</span>')
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border: 1px solid #ddd; overflow-x: auto; max-height: 500px;">{}</pre>',
                formatted_html
            )
        except Exception:
            return format_html('<pre>{}</pre>', str(obj.raw_payload))
    raw_payload_display.short_description = "Raw Payload (Debug)"
