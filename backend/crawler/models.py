from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()

class CrawlRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class CrawlRunTrigger(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    MANUAL = "manual", "Manual"


class CrawlRun(models.Model):
    """
    One discovery/crawl cycle. Fully separate from scraper ScrapeRun.
    Tracks domains discovered, queued, crawled, and prospects created.
    """

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crawl_runs", null=True, blank=True)
    trigger = models.CharField(
        max_length=20,
        choices=CrawlRunTrigger.choices,
        default=CrawlRunTrigger.SCHEDULED,
    )
    status = models.CharField(
        max_length=20,
        choices=CrawlRunStatus.choices,
        default=CrawlRunStatus.RUNNING,
    )
    task_id = models.CharField(max_length=255, blank=True, default="")
    error_text = models.TextField(blank=True, default="")
    stats = models.JSONField(blank=True, default=dict)
    config = models.JSONField(blank=True, default=dict, help_text="Snapshot for this run (max_domains_per_run, etc.)")
    domains_queued = models.PositiveIntegerField(default=0)
    prospects_created = models.PositiveIntegerField(default=0)
    prospects_updated = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["-started_at"])]

    def __str__(self) -> str:
        return f"CrawlRun {self.id} @ {self.started_at:%Y-%m-%d %H:%M} ({self.status})"


class CrawlSource(models.Model):
    """
    Stores discovery query configurations that feed the domain discovery queue.
    """

    SOURCE_TYPE_CHOICES = [
        ("search", "Search Engine"),
        ("directory", "Directory"),
        ("event_platform", "Event Platform"),
        ("ngo_directory", "NGO Directory"),
    ]

    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crawl_sources", null=True, blank=True)
    discovery_query = models.CharField(max_length=500)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES)
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    competitor_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords that indicate a site IS a competitor. Auto-derived from discovery_query if empty.",
    )
    competitor_org_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Org types to exclude e.g. ['translation_agency', 'lsp', 'localization_vendor']",
    )

    class Meta:
        indexes = [
            models.Index(fields=["enabled", "priority"]),
            models.Index(fields=["source_type", "enabled"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.source_type})"


class DiscoveredDomain(models.Model):
    """
    Queue of domains waiting to be crawled and analyzed.
    """

    CRAWL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("crawling", "Crawling"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    domain = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="discovered_domains", null=True, blank=True)
    source = models.ForeignKey(
        CrawlSource, on_delete=models.SET_NULL, null=True, related_name="domains"
    )
    crawl_status = models.CharField(
        max_length=20,
        choices=CRAWL_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    crawl_attempts = models.PositiveIntegerField(default=0)
    priority = models.IntegerField(default=5)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    error_text = models.TextField(blank=True, default="")
    source_url = models.URLField(
        max_length=2048,
        blank=True,
        default="",
        help_text="Landing page URL from discovery (e.g. Serper organic link); crawler visits this before the homepage when set.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["crawl_status", "priority"]),
            models.Index(fields=["next_attempt_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.domain


class WebsiteProfile(models.Model):
    """
    Aggregated analysis results per domain.
    """

    domain = models.OneToOneField(
        DiscoveredDomain, on_delete=models.CASCADE, related_name="profile"
    )
    org_name = models.CharField(max_length=255, blank=True, default="")
    org_type = models.CharField(max_length=100, blank=True, default="")
    detected_org_types = models.JSONField(default=list)
    detected_services = models.JSONField(default=list)
    languages_detected = models.JSONField(default=list)
    countries_detected = models.JSONField(default=list)
    international_signals = models.JSONField(default=list)
    event_names = models.JSONField(default=list)
    contact_emails = models.JSONField(default=list)
    contact_phones = models.JSONField(default=list)
    translation_need_score = models.IntegerField(default=0)
    gemini_translation_need_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="When set, scoring pipeline prefers this value over rule-based score_website().",
    )
    pages_crawled = models.IntegerField(default=0)
    analyzed_at = models.DateTimeField(auto_now=True)

    is_competitor = models.BooleanField(default=False)
    is_competitor_reason = models.CharField(max_length=500, blank=True, default="")
    excluded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["translation_need_score"]),
            models.Index(fields=["analyzed_at"]),
            models.Index(fields=["is_competitor"], name="crawler_web_is_comp_7a1b2c_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.domain.domain} ({self.translation_need_score})"


class CrawlRunDomainResult(models.Model):
    """
    Per-run, per-domain processing ledger.

    Can be linked to either a scraper ScrapeRun (legacy) or a crawler CrawlRun.
    Exactly one of run or crawl_run must be set.
    """

    STATE_CHOICES = [
        ("queued", "Queued"),
        ("crawled", "Crawled"),
        ("analyzed", "Analyzed"),
        ("scored", "Scored"),
        ("failed", "Failed"),
    ]

    run = models.ForeignKey(
        "scraper.ScrapeRun",
        on_delete=models.CASCADE,
        related_name="crawler_domain_results",
        null=True,
        blank=True,
    )
    crawl_run = models.ForeignKey(
        CrawlRun,
        on_delete=models.CASCADE,
        related_name="domain_results",
        null=True,
        blank=True,
    )
    domain = models.ForeignKey(
        DiscoveredDomain, on_delete=models.CASCADE, related_name="run_results"
    )

    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="queued")
    crawl_succeeded = models.BooleanField(default=False)
    crawl_error = models.TextField(blank=True, default="")
    pages_crawled = models.IntegerField(default=0)

    org_name = models.CharField(max_length=255, blank=True, default="")
    org_type = models.CharField(max_length=100, blank=True, default="")
    detected_org_types = models.JSONField(default=list)
    detected_services = models.JSONField(default=list)
    languages_detected = models.JSONField(default=list)
    countries_detected = models.JSONField(default=list)
    international_signals = models.JSONField(default=list)
    event_names = models.JSONField(default=list)
    contact_emails = models.JSONField(default=list)
    contact_phones = models.JSONField(default=list)

    score = models.IntegerField(default=0)
    score_label = models.CharField(max_length=20, blank=True, default="")
    prospect_created = models.BooleanField(default=False)
    prospect_updated = models.BooleanField(default=False)

    is_competitor = models.BooleanField(default=False)
    is_competitor_reason = models.CharField(max_length=500, blank=True, default="")

    processed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                condition=models.Q(run_id__isnull=False),
                fields=["run", "domain"],
                name="uniq_crawler_run_domain",
            ),
            models.UniqueConstraint(
                condition=models.Q(crawl_run_id__isnull=False),
                fields=["crawl_run", "domain"],
                name="uniq_crawler_crawl_run_domain",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "state"]),
            models.Index(fields=["crawl_run", "state"]),
            models.Index(fields=["processed_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"run={self.run_id} domain={self.domain.domain} state={self.state}"


class AISearchJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("generating", "Generating Queries"),
        ("searching", "Searching"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ai_search_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    seed_topic = models.CharField(max_length=500)
    industry = models.CharField(max_length=200, blank=True, default="")
    region = models.CharField(max_length=200, blank=True, default="")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    error_text = models.TextField(blank=True, default="")

    queries_generated = models.JSONField(default=list)
    domains_discovered = models.PositiveIntegerField(default=0)
    prospects_created = models.PositiveIntegerField(default=0)
    qualification_log = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"AISearchJob: {self.seed_topic} ({self.status})"


class AISearchResult(models.Model):
    job = models.ForeignKey(
        AISearchJob, on_delete=models.CASCADE, related_name="results"
    )
    domain = models.CharField(max_length=255)
    org_name = models.CharField(max_length=255, blank=True, default="")
    org_type = models.CharField(max_length=100, blank=True, default="")
    why_needs_translation = models.TextField(blank=True, default="")
    international_signals = models.JSONField(default=list)
    contact_email = models.CharField(max_length=255, blank=True, default="")
    raw_data = models.JSONField(default=dict)

    queued_domain = models.ForeignKey(
        "DiscoveredDomain",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_search_results",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.domain} (job={self.job_id})"


class EventProspect(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("converted", "Converted"),
        ("expired", "Expired"),
        ("irrelevant", "Irrelevant"),
    ]

    EVENT_TYPE_CHOICES = [
        ("conference", "Conference"),
        ("summit", "Summit"),
        ("trade_show", "Trade Show"),
        ("workshop", "Workshop"),
        ("diplomatic", "Diplomatic Meeting"),
        ("legal", "Legal Proceeding"),
        ("medical", "Medical Congress"),
        ("ngo", "NGO/Development Forum"),
        ("government", "Government Event"),
        ("other", "Other"),
    ]

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="event_prospects"
    )
    discovered_domain = models.ForeignKey(
        "DiscoveredDomain",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_prospects",
    )
    ai_search_result = models.ForeignKey(
        "AISearchResult",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_prospects",
    )

    event_name = models.CharField(max_length=500)
    event_type = models.CharField(
        max_length=50, choices=EVENT_TYPE_CHOICES, default="other"
    )
    organizer_name = models.CharField(max_length=255, blank=True, default="")
    organizer_domain = models.CharField(max_length=255, blank=True, default="")
    event_url = models.URLField(blank=True, default="")

    event_date = models.DateField(null=True, blank=True)
    event_date_raw = models.CharField(max_length=200, blank=True, default="")
    event_location = models.CharField(max_length=255, blank=True, default="")
    is_virtual = models.BooleanField(default=False)
    is_hybrid = models.BooleanField(default=False)

    languages_involved = models.JSONField(default=list)
    countries_involved = models.JSONField(default=list)
    expected_attendee_count = models.CharField(max_length=100, blank=True, default="")
    translation_services_needed = models.JSONField(default=list)
    translation_need_score = models.IntegerField(default=0)

    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.CharField(max_length=255, blank=True, default="")
    contact_phone = models.CharField(max_length=100, blank=True, default="")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="new"
    )
    urgency_score = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-urgency_score", "event_date"]
        indexes = [
            models.Index(fields=["event_date"], name="crawler_eve_event_d_8d3e4f_idx"),
            models.Index(fields=["status"], name="crawler_eve_status_9e4f5a_idx"),
            models.Index(fields=["urgency_score"], name="crawler_eve_urgency_a0b1c2_idx"),
            models.Index(
                fields=["event_type", "status"], name="crawler_eve_event_t_d3e4f5_idx"
            ),
        ]
        constraints = [
            # Matches event_processor.py's update_or_create() key exactly. Without
            # this, two concurrent analyze_domain_task runs for the same domain
            # (e.g. a manual re-trigger racing a scheduled run) could both pass
            # get_or_create's initial lookup and create duplicate rows for the same
            # event. Django's update_or_create retries on IntegrityError when a
            # matching unique constraint exists (since 4.1), so this closes the
            # race without needing an explicit lock at the call site.
            models.UniqueConstraint(
                fields=["event_name", "organizer_domain"],
                name="uniq_eventprospect_event_name_organizer_domain",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.event_name} ({self.event_date or 'date unknown'})"
