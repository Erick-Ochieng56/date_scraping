from django.db import models
from django.utils import timezone


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    REVIEWED = "reviewed", "Reviewed"
    SYNCED = "synced", "Synced"
    ERROR = "error", "Error"


class Lead(models.Model):
    """
    Source-of-truth lead record produced by scrapers and later synced to Perfex.
    """

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    # Where it came from (scraper/source system)
    source_name = models.CharField(max_length=100, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    source_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional source-specific identifier (listing id, etc.).",
    )

    # Contact / identity
    full_name = models.CharField(max_length=255, blank=True, default="")
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    position = models.CharField(
        max_length=255, blank=True, default="", help_text="Job title/position"
    )
    company = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(
        blank=True, default="", help_text="Website URL"
    )
    phone_raw = models.CharField(max_length=64, blank=True, default="")
    phone_e164 = models.CharField(
        max_length=32, blank=True, default="", help_text="Normalized E.164 number"
    )
    
    # Address fields
    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    country_code = models.CharField(
        max_length=2, blank=True, default="", help_text="ISO-3166 alpha-2"
    )
    zip_code = models.CharField(max_length=20, blank=True, default="")
    
    # Additional fields for translation events
    default_language = models.CharField(
        max_length=10, blank=True, default="", help_text="Default language code (e.g., 'en', 'es')"
    )
    lead_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, help_text="Estimated lead value"
    )

    # “Date scraping” payload fields (kept generic)
    event_date = models.DateField(blank=True, null=True)
    event_datetime = models.DateTimeField(blank=True, null=True)
    event_text = models.CharField(max_length=255, blank=True, default="")

    # Storage for raw extraction (for audit/debug + reprocessing)
    raw_payload = models.JSONField(blank=True, default=dict)
    raw_payload_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="SHA-256 of canonicalized raw_payload for dedupe/idempotency.",
    )

    status = models.CharField(
        max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_e164"]),
            models.Index(fields=["source_name", "source_ref"]),
        ]

    def __str__(self) -> str:
        label = self.full_name or "Lead"
        if self.email:
            return f"{label} <{self.email}>"
        if self.phone_e164:
            return f"{label} ({self.phone_e164})"
        return label
