from __future__ import annotations

from django.contrib import admin

from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSource,
    DiscoveredDomain,
    EventProspect,
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
    list_display = [
        "name",
        "discovery_query",
        "source_type",
        "enabled",
        "priority",
    ]
    list_filter = ["enabled", "source_type"]
    search_fields = ["name", "discovery_query"]
    fields = [
        "name",
        "owner",
        "discovery_query",
        "source_type",
        "enabled",
        "priority",
        "competitor_keywords",
        "competitor_org_types",
    ]
    actions = ["rederive_competitor_signals"]

    @admin.action(description="Re-derive competitor signals from query")
    def rederive_competitor_signals(self, request, queryset):
        from crawler.services.competitor_deriver import derive_competitor_signals

        for source in queryset:
            signals = derive_competitor_signals(source.discovery_query)
            source.competitor_keywords = signals.get("competitor_keywords", [])
            source.competitor_org_types = signals.get("competitor_org_types", [])
            source.save(
                update_fields=["competitor_keywords", "competitor_org_types"]
            )
        self.message_user(
            request, f"Re-derived signals for {queryset.count()} sources."
        )


@admin.register(DiscoveredDomain)
class DiscoveredDomainAdmin(admin.ModelAdmin):
    list_display = [
        "domain",
        "source_url",
        "crawl_status",
        "crawl_attempts",
        "first_seen_at",
        "priority",
    ]
    list_filter = ["crawl_status"]
    search_fields = ["domain"]
    ordering = ["crawl_status", "priority", "-first_seen_at"]

    @admin.action(description="Reset to pending")
    def reset_to_pending(self, request, queryset):
        queryset.update(crawl_status="pending", error_text="", next_attempt_at=None)

    @admin.action(description="Trigger crawl (create CrawlRun + enqueue)")
    def trigger_crawl(self, request, queryset):
        from django.utils import timezone

        from crawler.models import CrawlRun, CrawlRunDomainResult, CrawlRunTrigger
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
    list_display = [
        "domain",
        "org_name",
        "org_type",
        "translation_need_score",
        "is_competitor",
        "analyzed_at",
    ]
    list_filter = ["is_competitor", "org_type"]
    search_fields = ["org_name", "domain__domain"]
    ordering = ["-translation_need_score"]


@admin.register(AISearchJob)
class AISearchJobAdmin(admin.ModelAdmin):
    list_display = [
        "seed_topic",
        "region",
        "industry",
        "status",
        "domains_discovered",
        "created_at",
    ]
    readonly_fields = [
        "queries_generated",
        "domains_discovered",
        "prospects_created",
        "error_text",
        "created_at",
        "updated_at",
    ]
    actions = ["rerun_job"]

    @admin.action(description="Re-run selected AI search jobs")
    def rerun_job(self, request, queryset):
        from crawler.tasks import run_ai_search_job

        for job in queryset:
            job.status = "pending"
            job.error_text = ""
            job.save(update_fields=["status", "error_text", "updated_at"])
            run_ai_search_job.delay(job.id)
        self.message_user(request, f"Queued {queryset.count()} jobs.")


@admin.register(AISearchResult)
class AISearchResultAdmin(admin.ModelAdmin):
    list_display = ["domain", "org_name", "org_type", "job", "created_at"]
    search_fields = ["domain", "org_name"]
    raw_id_fields = ["job", "queued_domain"]


@admin.register(EventProspect)
class EventProspectAdmin(admin.ModelAdmin):
    list_display = [
        "event_name",
        "event_type",
        "organizer_domain",
        "event_date",
        "urgency_score",
        "translation_need_score",
        "status",
    ]
    list_filter = ["status", "event_type", "is_virtual"]
    search_fields = ["event_name", "organizer_name", "organizer_domain"]
    ordering = ["-urgency_score", "event_date"]
    raw_id_fields = ["owner", "discovered_domain", "ai_search_result"]
    actions = ["mark_contacted", "mark_irrelevant"]

    @admin.action(description="Mark as Contacted")
    def mark_contacted(self, request, queryset):
        queryset.update(status="contacted")

    @admin.action(description="Mark as Irrelevant")
    def mark_irrelevant(self, request, queryset):
        queryset.update(status="irrelevant")
