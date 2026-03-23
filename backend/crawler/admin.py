from __future__ import annotations

from django.contrib import admin

from crawler.models import (
    CrawlRun,
    CrawlRunStatus,
    CrawlSource,
    DiscoveredDomain,
    WebsiteProfile,
)


@admin.register(CrawlRun)
class CrawlRunAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "started_at",
        "finished_at",
        "status",
        "trigger",
        "domains_queued",
        "prospects_created",
        "prospects_updated",
    ]
    list_filter = ["status", "trigger"]
    ordering = ["-started_at"]
    readonly_fields = [
        "started_at",
        "finished_at",
        "task_id",
        "stats",
        "config",
        "domains_queued",
        "prospects_created",
        "prospects_updated",
    ]

    @admin.action(description="Trigger discovery now")
    def trigger_discovery(self, request, queryset):
        from crawler.tasks import discover_websites_task

        t = discover_websites_task.delay()
        self.message_user(
            request,
            f"Discovery task enqueued (task_id={t.id}). Check CrawlRun list for new run.",
        )

    actions = ["trigger_discovery"]


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

    @admin.action(description="Trigger crawl (create CrawlRun + enqueue)")
    def trigger_crawl(self, request, queryset):
        from django.utils import timezone

        from crawler.models import CrawlRun, CrawlRunDomainResult, CrawlRunStatus, CrawlRunTrigger
        from crawler.tasks import crawl_domain_task

        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.MANUAL,
            status=CrawlRunStatus.RUNNING,
            started_at=timezone.now(),
            domains_queued=queryset.count(),
        )
        for domain in queryset.values_list("id", flat=True):
            CrawlRunDomainResult.objects.get_or_create(
                crawl_run_id=run.id,
                domain_id=domain,
                defaults={"state": "queued"},
            )
            crawl_domain_task.delay(domain_id=int(domain), run_id=run.id)
        self.message_user(
            request,
            f"CrawlRun #{run.id} created; {queryset.count()} domain(s) enqueued.",
        )

    actions = ["reset_to_pending", "trigger_crawl"]


@admin.register(WebsiteProfile)
class WebsiteProfileAdmin(admin.ModelAdmin):
    list_display = ["domain", "org_name", "translation_need_score", "analyzed_at"]
    list_filter = ["detected_org_types"]
    search_fields = ["org_name", "domain__domain"]
    ordering = ["-translation_need_score"]
