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

    @admin.action(description="Trigger crawl (create run + enqueue)")
    def trigger_crawl(self, request, queryset):
        from django.utils import timezone

        from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeRunTrigger
        from tasks.crawler_tasks import _get_or_create_crawler_target, _initial_run_stats, crawl_domain_task

        target = _get_or_create_crawler_target()
        run = ScrapeRun.objects.create(
            target=target,
            trigger=ScrapeRunTrigger.MANUAL,
            status=ScrapeRunStatus.RUNNING,
            started_at=timezone.now(),
            stats=_initial_run_stats(),
            item_count=queryset.count(),
        )

        for domain in queryset.values_list("id", flat=True):
            crawl_domain_task.delay(domain_id=int(domain), run_id=run.id)

    actions = ["reset_to_pending", "trigger_crawl"]


@admin.register(WebsiteProfile)
class WebsiteProfileAdmin(admin.ModelAdmin):
    list_display = ["domain", "org_name", "translation_need_score", "analyzed_at"]
    list_filter = ["detected_org_types"]
    search_fields = ["org_name", "domain__domain"]
    ordering = ["-translation_need_score"]
