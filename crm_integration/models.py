from django.db import models
from django.utils import timezone

from leads.models import Lead


class PerfexSyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SYNCED = "synced", "Synced"
    ERROR = "error", "Error"


class PerfexLeadSync(models.Model):
    """
    Tracks Perfex-side identity and sync status for a Lead.

    Perfex credentials/config are kept in environment variables, not DB.
    """

    lead = models.OneToOneField(
        Lead, on_delete=models.CASCADE, related_name="perfex_sync"
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    perfex_lead_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=PerfexSyncStatus.choices, default=PerfexSyncStatus.PENDING
    )
    last_sync_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(blank=True, null=True)

    payload_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Hash of last successfully synced payload for idempotency.",
    )
    last_payload = models.JSONField(blank=True, default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["perfex_lead_id"]),
        ]

    def __str__(self) -> str:
        return f"PerfexSync({self.lead_id}) [{self.status}]"
