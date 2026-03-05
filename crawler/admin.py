from __future__ import annotations

from django.contrib import admin

from crawler.models import CrawlSource, DiscoveredDomain, WebsiteProfile


@admin.register(CrawlSource)
class CrawlSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "source_type", "enabled", "priority"]
    list_filter = ["enabled", "source_type"]
    search_fields = ["name", "discovery_query"]


@admin.register(DiscoveredDomain)
class DiscoveredDomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "crawl_status", "crawl_attempts", "first_seen_at", "priority"]
    list_filter = ["crawl_status"]
    search_fields = ["domain"]
    ordering = ["crawl_status", "priority", "-first_seen_at"]

    @admin.action(description="Reset to pending")
    def reset_to_pending(self, request, queryset):
        queryset.update(crawl_status="pending", error_text="", next_attempt_at=None)

    actions = ["reset_to_pending"]


@admin.register(WebsiteProfile)
class WebsiteProfileAdmin(admin.ModelAdmin):
    list_display = ["domain", "org_name", "translation_need_score", "analyzed_at"]
    list_filter = ["detected_org_types"]
    search_fields = ["org_name", "domain__domain"]
    ordering = ["-translation_need_score"]
