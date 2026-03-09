from __future__ import annotations

from django.db import models


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
    discovery_query = models.CharField(max_length=500)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES)
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

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
    pages_crawled = models.IntegerField(default=0)
    analyzed_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["translation_need_score"]),
            models.Index(fields=["analyzed_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.domain.domain} ({self.translation_need_score})"


class CrawlRunDomainResult(models.Model):
    """
    Per-run, per-domain processing ledger.

    This enables idempotent stats and reliable ScrapeRun finalization even if
    Celery tasks retry.
    """

    STATE_CHOICES = [
        ("queued", "Queued"),
        ("crawled", "Crawled"),
        ("analyzed", "Analyzed"),
        ("scored", "Scored"),
        ("failed", "Failed"),
    ]

    run = models.ForeignKey(
        "scraper.ScrapeRun", on_delete=models.CASCADE, related_name="crawler_domain_results"
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

    processed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "domain"], name="uniq_crawler_run_domain")
        ]
        indexes = [
            models.Index(fields=["run", "state"]),
            models.Index(fields=["processed_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"run={self.run_id} domain={self.domain.domain} state={self.state}"
