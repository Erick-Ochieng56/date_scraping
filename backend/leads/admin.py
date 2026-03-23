import json

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Lead, LeadStatus, Prospect, ProspectStatus


# Prospect Admin Actions
@admin.action(description="Mark selected prospects as Contacted")
def mark_prospect_contacted(modeladmin, request, queryset):
    now = timezone.now()
    queryset.filter(status=ProspectStatus.NEW).update(
        status=ProspectStatus.CONTACTED,
        contacted_at=now,
    )


@admin.action(description="Convert selected prospects to Leads")
def convert_prospects_to_leads(modeladmin, request, queryset):
    """Convert Prospects to Leads for full CRM workflow."""
    count = 0
    for prospect in queryset.filter(status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED]):
        try:
            prospect.convert_to_lead()
            count += 1
        except Exception as e:
            modeladmin.message_user(
                request,
                f"Error converting prospect {prospect.id}: {e}",
                level="error"
            )
    modeladmin.message_user(
        request,
        f"Converted {count} prospect(s) to leads.",
        level="success"
    )


@admin.action(description="Mark selected prospects as Rejected")
def mark_prospect_rejected(modeladmin, request, queryset):
    now = timezone.now()
    queryset.filter(
        status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED]
    ).update(
        status=ProspectStatus.REJECTED,
        rejected_at=now,
    )


# Lead Admin Actions
@admin.action(description="Mark selected leads as Interested")
def mark_interested(modeladmin, request, queryset):
    queryset.filter(status=LeadStatus.CONTACTED).update(
        status=LeadStatus.INTERESTED,
    )


@admin.action(description="Mark selected leads as Rejected")
def mark_lead_rejected(modeladmin, request, queryset):
    now = timezone.now()
    queryset.filter(
        status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED]
    ).update(
        status=LeadStatus.REJECTED,
        rejected_at=now,
    )


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    """Admin for Prospects (pre-contact discovery records)."""
    list_display = (
        "id",
        "status",
        "event_name",
        "company",
        "email",
        "phone_e164",
        "website",
        "source_name",
        "contacted_at",
        "converted_at",
        "rejected_at",
        "created_at",
    )
    list_filter = ("status", "source_name")
    search_fields = ("event_name", "company", "email", "phone_e164", "source_ref")
    actions = [mark_prospect_contacted, convert_prospects_to_leads, mark_prospect_rejected]
    readonly_fields = ("created_at", "updated_at", "raw_payload_hash", "raw_payload_display", "converted_at")
    
    fieldsets = (
        ("Discovery Information", {
            "fields": ("event_name", "company", "email", "phone_raw", "phone_e164", "website")
        }),
        ("Source Information", {
            "fields": ("source_name", "source_url", "source_ref")
        }),
        ("Status & Notes", {
            "fields": ("status", "notes", "contacted_at", "rejected_at", "converted_at")
        }),
        ("Debug Information", {
            "fields": ("raw_payload_display", "raw_payload_hash"),
            "classes": ("collapse",),
            "description": "Raw extracted data for debugging."
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
        
        try:
            formatted = json.dumps(obj.raw_payload, indent=2, ensure_ascii=False)
            formatted_html = formatted.replace('""', '<span style="color: red; font-weight: bold;">""</span>')
            formatted_html = formatted_html.replace('null', '<span style="color: orange;">null</span>')
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border: 1px solid #ddd; overflow-x: auto; max-height: 500px;">{}</pre>',
                formatted_html
            )
        except Exception:
            return format_html('<pre>{}</pre>', str(obj.raw_payload))
    raw_payload_display.short_description = "Raw Payload (Debug)"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Admin for Leads (post-contact qualified records)."""
    list_display = (
        "id",
        "status",
        "prospect",
        "event_name",
        "company",
        "source_name",
        "full_name",
        "email",
        "phone_e164",
        "event_date",
        "contacted_at",
        "rejected_at",
        "created_at",
    )
    list_filter = ("status", "source_name", "country_code")
    search_fields = ("event_name", "full_name", "email", "phone_e164", "source_ref", "company")
    actions = [mark_interested, mark_lead_rejected]
    readonly_fields = ("created_at", "updated_at", "raw_payload_hash", "raw_payload_display", "prospect")
    
    fieldsets = (
        ("Source", {
            "fields": ("prospect", "source_name", "source_url", "source_ref")
        }),
        ("Contact Information", {
            "fields": ("full_name", "email", "phone_raw", "phone_e164", "company", "position", "website")
        }),
        ("Address", {
            "fields": ("address", "city", "state", "zip_code", "country_code")
        }),
        ("Event Information", {
            "fields": ("event_date", "event_datetime", "event_name")
        }),
        ("Additional", {
            "fields": ("default_language", "lead_value", "status", "notes")
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
