from django.db import models
from django.utils import timezone


class ScrapeTargetType(models.TextChoices):
    HTML = "html", "HTML (requests/bs4)"
    PLAYWRIGHT = "playwright", "Playwright (browser automation)"


class ScrapeRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class ScrapeRunTrigger(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    MANUAL = "manual", "Manual"


class ScrapeTarget(models.Model):
    """
    A configured source to scrape.

    `config` is intentionally flexible (CSS selectors, pagination rules, etc.).
    """

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=200, unique=True)
    enabled = models.BooleanField(default=True)
    target_type = models.CharField(
        max_length=20, choices=ScrapeTargetType.choices, default=ScrapeTargetType.HTML
    )
    start_url = models.URLField()
    run_every_minutes = models.PositiveIntegerField(
        default=60, help_text="Beat schedule interval (minutes)."
    )
    config = models.JSONField(blank=True, default=dict)
    last_run_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class ScrapeRun(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    target = models.ForeignKey(
        ScrapeTarget, on_delete=models.CASCADE, related_name="runs"
    )
    trigger = models.CharField(
        max_length=20, choices=ScrapeRunTrigger.choices, default=ScrapeRunTrigger.MANUAL
    )
    status = models.CharField(
        max_length=20, choices=ScrapeRunStatus.choices, default=ScrapeRunStatus.RUNNING
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)

    task_id = models.CharField(max_length=255, blank=True, default="")
    error_text = models.TextField(blank=True, default="")
    stats = models.JSONField(blank=True, default=dict)
    item_count = models.PositiveIntegerField(default=0)
    created_leads = models.PositiveIntegerField(default=0)
    updated_leads = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["target", "started_at"])]

    def __str__(self) -> str:
        return f"{self.target.name} @ {self.started_at:%Y-%m-%d %H:%M:%S} ({self.status})"
