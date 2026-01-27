from django.contrib import admin

from .models import ScrapeRun, ScrapeTarget


@admin.register(ScrapeTarget)
class ScrapeTargetAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "enabled", "target_type", "run_every_minutes", "last_run_at")
    list_filter = ("enabled", "target_type")
    search_fields = ("name", "start_url")


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
    )
    list_filter = ("status", "trigger", "target")
    search_fields = ("target__name", "error_text", "task_id")
    readonly_fields = ("created_at", "updated_at", "started_at")
