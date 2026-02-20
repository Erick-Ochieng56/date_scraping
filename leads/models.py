from django.db import models
from django.utils import timezone


class ProspectStatus(models.TextChoices):
    NEW = "new", "New"  # Just scraped, awaiting review
    CONTACTED = "contacted", "Contacted"  # Team has reached out
    CONVERTED = "converted", "Converted"  # Converted to Lead
    REJECTED = "rejected", "Rejected"  # Not interested — closed


class LeadStatus(models.TextChoices):
    CONTACTED = "contacted", "Contacted"  # Team has reached out
    INTERESTED = "interested", "Interested"  # Org confirmed interest → ready for CRM
    REJECTED = "rejected", "Rejected"  # Org not interested — closed
    SYNCED = "synced", "Synced"  # Pushed to Perfex CRM
    ERROR = "error", "Error"  # Sync/processing failure


class Prospect(models.Model):
    """
    Pre-contact discovery record: basic info scraped from events/meetings.

    Contains minimal fields needed for initial discovery:
    - Event Name
    - Company/Organisation Name
    - Email
    - Phone Number
    - Website

    Once contacted, Prospects can be converted to Leads for full CRM workflow.
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

    # Minimal discovery fields (pre-contact)
    event_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Name of the event or meeting that was scraped.",
    )
    company = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, null=True)
    phone_raw = models.CharField(max_length=64, blank=True, default="")
    phone_e164 = models.CharField(
        max_length=32, blank=True, default="", help_text="Normalized E.164 number"
    )
    website = models.URLField(blank=True, default="", help_text="Website URL")

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
        max_length=20, choices=ProspectStatus.choices, default=ProspectStatus.NEW
    )
    notes = models.TextField(blank=True, default="")
    contacted_at = models.DateTimeField(
        blank=True, null=True, help_text="When the team first reached out."
    )
    converted_at = models.DateTimeField(
        blank=True, null=True, help_text="When converted to Lead."
    )
    rejected_at = models.DateTimeField(
        blank=True, null=True, help_text="When marked as not interested."
    )

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_e164"]),
            models.Index(fields=["source_name", "source_ref"]),
            models.Index(fields=["status"]),
        ]

    def mark_contacted(self, save=True):
        self.status = ProspectStatus.CONTACTED
        self.contacted_at = self.contacted_at or timezone.now()
        if save:
            self.save(update_fields=["status", "contacted_at", "updated_at"])

    def mark_rejected(self, reason="", save=True):
        self.status = ProspectStatus.REJECTED
        self.rejected_at = timezone.now()
        if reason:
            self.notes = (
                self.notes + "\n" if self.notes else ""
            ) + f"Rejected: {reason}"
        if save:
            self.save(update_fields=["status", "rejected_at", "notes", "updated_at"])

    def convert_to_lead(self, **extra_fields) -> "Lead":
        """
        Convert this Prospect to a Lead with full post-contact fields.

        Args:
            **extra_fields: Additional fields to set on the Lead (e.g., full_name, position, address)

        Returns:
            Lead: The newly created Lead object

        Raises:
            ValueError: If prospect is already converted or rejected
        """
        if self.status == ProspectStatus.CONVERTED:
            raise ValueError(f"Prospect {self.id} is already converted to a Lead.")
        if self.status == ProspectStatus.REJECTED:
            raise ValueError(f"Prospect {self.id} is rejected and cannot be converted.")

        # Use the Lead class that's defined in the same module
        lead = Lead.objects.create(
            prospect=self,
            # Copy basic fields from Prospect
            source_name=self.source_name,
            source_url=self.source_url,
            source_ref=self.source_ref,
            company=self.company,
            email=self.email,
            phone_raw=self.phone_raw,
            phone_e164=self.phone_e164,
            website=self.website,
            event_name=self.event_name,
            raw_payload=self.raw_payload,
            raw_payload_hash=self.raw_payload_hash,
            status=LeadStatus.CONTACTED,
            contacted_at=self.contacted_at or timezone.now(),
            notes=self.notes,
            # Allow additional fields to be passed (e.g., full_name, position, address from contact)
            **extra_fields,
        )

        # Mark prospect as converted
        self.status = ProspectStatus.CONVERTED
        self.converted_at = timezone.now()
        self.save(update_fields=["status", "converted_at", "updated_at"])

        # Sync successful Lead to Google Sheets (only if has meaningful data)
        self._sync_lead_to_sheets(lead)

        return lead

    def _sync_lead_to_sheets(self, lead: "Lead") -> None:
        """
        Sync a successful Lead to Google Sheets.
        Only syncs if Lead has meaningful data (not all blank fields).
        """
        import os

        # Check if Sheets sync is enabled
        gsheets_enabled = os.getenv("GSHEETS_ENABLED", "1")
        if gsheets_enabled.strip().lower() not in {"1", "true", "t", "yes", "y", "on"}:
            return

        # Validate Lead has meaningful data
        has_name = lead.full_name and str(lead.full_name).strip()
        has_company = lead.company and str(lead.company).strip()
        has_email = lead.email and str(lead.email).strip()

        # Need at least one of: name, company, or email
        if not (has_name or has_company or has_email):
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"Skipping Sheets sync for Lead {lead.id}: no meaningful data "
                f"(name='{lead.full_name}', company='{lead.company}', email='{lead.email}')"
            )
            return

        # Lead has data, queue sync to Sheets
        try:
            from sheets_integration.tasks import append_lead_to_sheet

            append_lead_to_sheet.delay(lead.id)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Could not queue Sheets sync for Lead {lead.id}: {e}")

    def __str__(self) -> str:
        label = self.company or "Prospect"
        if self.event_name:
            label = f"{self.event_name} — {label}"
        if self.email:
            return f"{label} <{self.email}>"
        if self.phone_raw:
            return f"{label} ({self.phone_raw})"
        return label


class Lead(models.Model):
    """
    Post-contact qualified lead record with full CRM fields.

    Leads are created from Prospects after initial contact, or can be created manually.
    Contains all fields needed for CRM integration and sales workflow.
    """

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    # Reference to source Prospect (if converted from Prospect)
    prospect = models.ForeignKey(
        "Prospect",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        help_text="Source Prospect this Lead was converted from (if applicable).",
    )

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
    website = models.URLField(blank=True, default="", help_text="Website URL")
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
        max_length=10,
        blank=True,
        default="",
        help_text="Default language code (e.g., 'en', 'es')",
    )
    lead_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated lead value",
    )

    # "Date scraping" payload fields (kept generic)
    event_date = models.DateField(blank=True, null=True)
    event_datetime = models.DateTimeField(blank=True, null=True)
    event_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Name of the event or meeting that was scraped.",
    )

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
        max_length=20, choices=LeadStatus.choices, default=LeadStatus.CONTACTED
    )
    notes = models.TextField(blank=True, default="")
    contacted_at = models.DateTimeField(
        blank=True, null=True, help_text="When the team first reached out."
    )
    rejected_at = models.DateTimeField(
        blank=True, null=True, help_text="When the prospect was marked not interested."
    )

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_e164"]),
            models.Index(fields=["source_name", "source_ref"]),
            models.Index(fields=["status"]),
            models.Index(fields=["event_date"]),
            models.Index(fields=["prospect"]),
        ]

    def mark_interested(self, save=True):
        self.status = LeadStatus.INTERESTED
        if save:
            self.save(update_fields=["status", "updated_at"])

    def mark_rejected(self, reason="", save=True):
        self.status = LeadStatus.REJECTED
        self.rejected_at = timezone.now()
        if reason:
            self.notes = (
                self.notes + "\n" if self.notes else ""
            ) + f"Rejected: {reason}"
        if save:
            self.save(update_fields=["status", "rejected_at", "notes", "updated_at"])

    def __str__(self) -> str:
        label = self.company or self.full_name or "Lead"
        if self.event_name:
            label = f"{self.event_name} — {label}"
        if self.email:
            return f"{label} <{self.email}>"
        if self.phone_raw:
            return f"{label} ({self.phone_raw})"
        return label
