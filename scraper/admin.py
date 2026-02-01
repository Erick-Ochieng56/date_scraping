from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import ScrapeRun, ScrapeRunTrigger, ScrapeTarget
from scraper.tasks import scrape_target


class ScrapeTargetAdminForm(forms.ModelForm):
    """Custom form with config validation."""
    
    class Meta:
        model = ScrapeTarget
        fields = "__all__"
    
    def clean_config(self):
        """Validate that config has required fields."""
        config = self.cleaned_data.get("config") or {}
        
        # Check for required config fields
        item_selector = config.get("item_selector") or config.get("items_selector")
        if not item_selector:
            raise ValidationError(
                "Config must include 'item_selector' (CSS selector for items to scrape). "
                "Example: {\"item_selector\": \".event-card\", \"fields\": {...}}"
            )
        
        fields = config.get("fields") or {}
        if not fields:
            raise ValidationError(
                "Config must include 'fields' (mapping of field names to CSS selectors). "
                "Example: {\"fields\": {\"full_name\": \".title\", \"event_date\": \".date\"}}"
            )
        
        return config


@admin.register(ScrapeTarget)
class ScrapeTargetAdmin(admin.ModelAdmin):
    form = ScrapeTargetAdminForm
    list_display = (
        "id",
        "name",
        "enabled",
        "target_type",
        "run_every_minutes",
        "last_run_at",
        "actions_column",
    )
    list_filter = ("enabled", "target_type")
    search_fields = ("name", "start_url")
    readonly_fields = ("created_at", "updated_at", "last_run_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "enabled", "start_url", "target_type")
        }),
        ("Schedule", {
            "fields": ("run_every_minutes",)
        }),
        ("Configuration", {
            "fields": ("config",),
            "description": "JSON configuration with selectors and scraping rules"
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at", "last_run_at"),
            "classes": ("collapse",)
        }),
    )

    actions = [
        "enable_targets",
        "disable_targets",
        "trigger_scrape_selected",
        "sync_from_config",
    ]

    def changelist_view(self, request, extra_context=None):
        """Add custom context for changelist."""
        extra_context = extra_context or {}
        extra_context["auto_create_url"] = reverse("admin:scraper_scrapetarget_auto_create")
        extra_context["show_auto_create"] = True
        return super().changelist_view(request, extra_context)
    
    def add_view(self, request, form_url="", extra_context=None):
        """Override add view to show auto-create option."""
        extra_context = extra_context or {}
        extra_context["auto_create_url"] = reverse("admin:scraper_scrapetarget_auto_create")
        return super().add_view(request, form_url, extra_context)

    def actions_column(self, obj):
        """Custom column with action buttons."""
        trigger_url = reverse("admin:scraper_scrapetarget_trigger", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; display: inline-block;">Test Scrape</a>',
            trigger_url
        )
    actions_column.short_description = "Quick Actions"

    def enable_targets(self, request, queryset):
        """Admin action to enable selected targets."""
        count = queryset.update(enabled=True)
        self.message_user(request, f"{count} target(s) enabled.", messages.SUCCESS)
    enable_targets.short_description = "Enable selected targets"

    def disable_targets(self, request, queryset):
        """Admin action to disable selected targets."""
        count = queryset.update(enabled=False)
        self.message_user(request, f"{count} target(s) disabled.", messages.SUCCESS)
    disable_targets.short_description = "Disable selected targets"

    def trigger_scrape_selected(self, request, queryset):
        """Admin action to trigger scrape for selected targets."""
        count = 0
        for target in queryset:
            if target.enabled:
                scrape_target.delay(target_id=target.id, trigger=ScrapeRunTrigger.MANUAL)
                count += 1
        self.message_user(
            request,
            f"Scrape triggered for {count} target(s).",
            messages.SUCCESS
        )
    trigger_scrape_selected.short_description = "Trigger scrape for selected targets"

    def sync_from_config(self, request, queryset):
        """Admin action to sync targets from config file."""
        from django.core.management import call_command
        from io import StringIO
        
        output = StringIO()
        try:
            call_command("sync_targets", file="targets.json", update=True, stdout=output)
            output_str = output.getvalue()
            self.message_user(
                request,
                f"Targets synced successfully. {output_str}",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Failed to sync targets: {str(e)}",
                messages.ERROR
            )
    sync_from_config.short_description = "Sync targets from targets.json"

    def get_urls(self):
        """Add custom URLs for admin actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:target_id>/trigger/",
                self.admin_site.admin_view(self.trigger_scrape_view),
                name="scraper_scrapetarget_trigger",
            ),
            path(
                "auto-create/",
                self.admin_site.admin_view(self.auto_create_view),
                name="scraper_scrapetarget_auto_create",
            ),
        ]
        return custom_urls + urls

    def trigger_scrape_view(self, request, target_id):
        """Custom view to trigger a scrape for a single target."""
        try:
            target = ScrapeTarget.objects.get(pk=target_id)
            scrape_target.delay(target_id=target.id, trigger=ScrapeRunTrigger.MANUAL)
            self.message_user(
                request,
                f"Scrape triggered for '{target.name}'. Check ScrapeRun for results.",
                messages.SUCCESS
            )
        except ScrapeTarget.DoesNotExist:
            self.message_user(request, "Target not found.", messages.ERROR)
        
        return HttpResponseRedirect(reverse("admin:scraper_scrapetarget_changelist"))

    def auto_create_view(self, request):
        """Custom view to auto-create a target from URL."""
        from scraper.services.auto_discover import auto_create_target, detect_platform_type
        
        url = request.GET.get("url") or request.POST.get("url")
        name = request.GET.get("name") or request.POST.get("name") or None
        
        if not url:
            self.message_user(
                request,
                "Please provide a URL. Usage: /admin/scraper/scrapetarget/auto-create/?url=https://example.com",
                messages.WARNING
            )
            return HttpResponseRedirect(reverse("admin:scraper_scrapetarget_changelist"))
        
        try:
            # Check if target with this name already exists
            if name:
                existing = ScrapeTarget.objects.filter(name=name).first()
                if existing:
                    self.message_user(
                        request,
                        f"Target with name '{name}' already exists. Redirecting to edit page.",
                        messages.WARNING
                    )
                    return HttpResponseRedirect(
                        reverse("admin:scraper_scrapetarget_change", args=[existing.pk])
                    )
            
            # Auto-discover and create
            target_config = auto_create_target(url, name)
            platform = detect_platform_type(url)
            
            target = ScrapeTarget.objects.create(
                name=target_config["name"],
                start_url=target_config["start_url"],
                enabled=target_config["enabled"],
                target_type=target_config["target_type"],
                run_every_minutes=target_config["run_every_minutes"],
                config=target_config["config"],
            )
            
            platform_msg = f" (Platform: {platform})" if platform else " (Generic config)"
            self.message_user(
                request,
                f"Target '{target.name}' created successfully{platform_msg}. "
                f"Please review and adjust the configuration if needed.",
                messages.SUCCESS
            )
            return HttpResponseRedirect(
                reverse("admin:scraper_scrapetarget_change", args=[target.pk])
            )
        except Exception as e:
            self.message_user(
                request,
                f"Failed to create target: {str(e)}",
                messages.ERROR
            )
            return HttpResponseRedirect(reverse("admin:scraper_scrapetarget_changelist"))


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target",
        "trigger",
        "status",
        "started_at",
        "finished_at",
        "item_count",
        "created_leads",
        "updated_leads",
        "error_preview",
    )
    list_filter = ("status", "trigger", "target")
    search_fields = ("target__name", "error_text", "task_id")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at", "task_id")
    actions = ["retry_failed_runs"]
    
    def retry_failed_runs(self, request, queryset):
        """Retry failed scrape runs."""
        from scraper.tasks import scrape_target
        
        count = 0
        for run in queryset.filter(status="failed"):
            if run.target.enabled:
                scrape_target.delay(target_id=run.target.id, trigger="manual")
                count += 1
        
        self.message_user(
            request,
            f"Retried {count} failed scrape(s).",
            messages.SUCCESS
        )
    retry_failed_runs.short_description = "Retry selected failed runs"
    
    def error_preview(self, obj):
        """Show error message preview in list view."""
        if obj.status == "failed" and obj.error_text:
            # Truncate long errors
            error = obj.error_text[:100] + "..." if len(obj.error_text) > 100 else obj.error_text
            # Highlight common error types
            if "DNS" in error or "resolve" in error.lower() or "getaddrinfo" in error:
                return format_html('<span style="color: orange;">🌐 Network/DNS: {}</span>', error)
            elif "timeout" in error.lower():
                return format_html('<span style="color: orange;">⏱️ Timeout: {}</span>', error)
            elif "selector" in error.lower() or "css" in error.lower():
                return format_html('<span style="color: red;">🎯 Selector: {}</span>', error)
            elif "config" in error.lower():
                return format_html('<span style="color: red;">⚙️ Config: {}</span>', error)
            return format_html('<span style="color: red;">❌ {}</span>', error)
        return "-"
    error_preview.short_description = "Error"
    
    fieldsets = (
        ("Run Information", {
            "fields": ("target", "trigger", "status", "task_id")
        }),
        ("Timing", {
            "fields": ("started_at", "finished_at")
        }),
        ("Results", {
            "fields": ("item_count", "created_leads", "updated_leads", "stats")
        }),
        ("Error Information", {
            "fields": ("error_text",),
            "description": "Click to expand and see full error details"
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
