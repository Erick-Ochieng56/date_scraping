from __future__ import annotations

import logging
import os
from pathlib import Path

from celery import shared_task
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeRunTrigger, ScrapeTarget
from scraper.services.runner import run_target
from scraper.services.upsert import upsert_prospect_from_item

logger = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    """Helper to get environment variable."""
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _enqueue_perfex_sync(lead_id: int) -> None:
    if not _get_bool("PERFEX_SYNC_ENABLED", default=False):
        return
    # Lazy import to avoid cyclic imports at module import time.
    from crm_integration.models import PerfexLeadSync
    from crm_integration.tasks import sync_lead_to_perfex

    PerfexLeadSync.objects.get_or_create(lead_id=lead_id)
    sync_lead_to_perfex.delay(lead_id=lead_id)


def _is_prospect_successful(prospect) -> bool:
    """
    Check if a prospect has meaningful data worth syncing to Google Sheets.

    Returns True if prospect has at least event_name OR company filled.
    Returns False if all key fields are blank/empty.
    """
    has_event = prospect.event_name and str(prospect.event_name).strip()
    has_company = prospect.company and str(prospect.company).strip()

    # At minimum, need event name or company to be considered successful
    return has_event or has_company


def _enqueue_sheets_sync(prospect_id: int, is_prospect: bool = True) -> None:
    """
    Enqueue Google Sheets sync only for successful prospects with actual data.

    This ensures we only log prospects that have meaningful information,
    not blank/empty records from failed scraping.
    """
    if not _get_bool("GSHEETS_ENABLED", default=True):
        return

    # Validate prospect has data before syncing
    from leads.models import Prospect

    try:
        prospect = Prospect.objects.get(id=prospect_id)

        # Only sync if prospect has meaningful data
        if not _is_prospect_successful(prospect):
            logger.debug(
                f"Skipping Sheets sync for Prospect {prospect_id}: no meaningful data "
                f"(event_name='{prospect.event_name}', company='{prospect.company}')"
            )
            return

        # Prospect has data, sync to Sheets
        from sheets_integration.tasks import append_prospect_to_sheet

        append_prospect_to_sheet.delay(prospect_id=prospect_id)
        logger.debug(f"Queued Sheets sync for Prospect {prospect_id}")

    except Prospect.DoesNotExist:
        logger.warning(f"Cannot sync Prospect {prospect_id} to Sheets: not found")


@shared_task
def enqueue_enabled_targets() -> int:
    """
    Periodic entrypoint: enqueue scrape tasks for all enabled targets.
    """
    target_ids = list(
        ScrapeTarget.objects.filter(enabled=True).values_list("id", flat=True)
    )
    for target_id in target_ids:
        scrape_target.delay(target_id=target_id, trigger=ScrapeRunTrigger.SCHEDULED)
    return len(target_ids)


@shared_task(bind=True)
def scrape_target(self, target_id: int, trigger: str = ScrapeRunTrigger.MANUAL) -> int:
    """
    Scrape a single target and upsert leads.
    Returns number of items extracted.
    """
    target = ScrapeTarget.objects.get(id=target_id)
    run = ScrapeRun.objects.create(
        target=target,
        trigger=trigger,
        status=ScrapeRunStatus.RUNNING,
        started_at=timezone.now(),
        task_id=getattr(self.request, "id", "") or "",
    )

    created_count = 0
    updated_count = 0
    items: list[dict] = []

    try:
        # Validate target config before attempting scrape
        cfg = target.config or {}
        item_selector = cfg.get("item_selector") or cfg.get("items_selector")
        if not item_selector:
            raise ValueError(
                f"ScrapeTarget '{target.name}' (ID: {target.id}) is missing required config.item_selector. "
                f"Please configure the target in Django admin before running."
            )

        items = run_target(target)
        run.item_count = len(items)

        with transaction.atomic():
            for item in items:
                prospect, created = upsert_prospect_from_item(target=target, item=item)
                if created:
                    created_count += 1
                    # Only push NEW prospects to Sheets. Do not re-push on updates.
                    _enqueue_sheets_sync(prospect.id, is_prospect=True)
                else:
                    updated_count += 1
                    # Existing prospect re-scraped. Keep its current status. Do not touch Sheets.

        run.created_leads = created_count  # Note: stores prospect count
        run.updated_leads = updated_count  # Note: stores prospect count
        run.status = ScrapeRunStatus.SUCCESS
        target.last_run_at = timezone.now()
        target.save(update_fields=["last_run_at"])
        return run.item_count
    except Exception as exc:
        error_msg = str(exc)
        error_lower = error_msg.lower()
        logger.exception("Scrape failed for target_id=%s: %s", target_id, error_msg)
        run.status = ScrapeRunStatus.FAILED
        run.error_text = error_msg

        # Categorize errors for better handling
        is_network_error = (
            "dns" in error_lower
            or "resolve" in error_lower
            or "getaddrinfo" in error_lower
            or "connection" in error_lower
            or "name_not_resolved" in error_lower
            or "err_name_not_resolved" in error_lower
        )

        is_timeout_error = "timeout" in error_lower

        is_config_error = (
            "missing" in error_lower
            and "config" in error_lower
            or "selector" in error_lower
            or "css" in error_lower
        )

        # Don't re-raise network/timeout errors - allow other targets to continue
        # But still mark this run as failed
        if is_network_error:
            logger.warning(
                "Target %s failed due to network/DNS issue. Check internet connection. "
                "Error: %s",
                target_id,
                error_msg[:200],
            )
            # Don't re-raise - let other targets run
            return 0
        elif is_timeout_error:
            logger.warning(
                "Target %s timed out. Consider increasing timeout_seconds in config. "
                "Error: %s",
                target_id,
                error_msg[:200],
            )
            # Don't re-raise - let other targets run
            return 0
        elif is_config_error:
            logger.warning(
                "Target %s has invalid configuration. Disable it or fix the config in admin. "
                "Error: %s",
                target_id,
                error_msg[:200],
            )
            # Don't re-raise - let other targets run
            return 0

        # For other errors, re-raise to ensure they're logged properly
        raise
    finally:
        run.finished_at = timezone.now()
        run.stats = {
            "created": created_count,
            "updated": updated_count,
        }
        run.save()


@shared_task
def sync_targets_from_config() -> dict:
    """
    Periodically sync targets from config file.

    This task reads targets.json (or path from TARGETS_SYNC_FILE env var)
    and syncs targets using the sync_targets management command.

    Set TARGETS_SYNC_ENABLED=true to enable periodic syncing.
    Set TARGETS_SYNC_FILE to specify config file path (default: targets.json).
    """
    if not _get_bool("TARGETS_SYNC_ENABLED", default=False):
        logger.debug("Target sync disabled (TARGETS_SYNC_ENABLED not set)")
        return {"synced": 0, "reason": "disabled"}

    config_file = Path(_get_env("TARGETS_SYNC_FILE", "targets.json") or "targets.json")
    if not config_file.exists():
        logger.warning(f"Targets config file not found: {config_file}")
        return {"synced": 0, "error": f"File not found: {config_file}"}

    try:
        # Use StringIO to capture command output (optional, for logging)
        from io import StringIO

        output = StringIO()

        # Call the management command
        call_command(
            "sync_targets",
            file=str(config_file),
            update=True,
            stdout=output,
        )

        output_str = output.getvalue()
        logger.info(f"Target sync completed: {output_str}")

        return {
            "synced": 1,
            "file": str(config_file),
            "message": "Targets synced successfully",
        }
    except Exception as exc:
        logger.exception("Failed to sync targets from config")
        return {"synced": 0, "error": str(exc), "file": str(config_file)}


@shared_task
def enrich_prospect_detail(
    prospect_id: int, platform: str = "generic", use_playwright: bool = False
) -> dict:
    """
    Two-Stage Scraping - Stage 2: Visit detail page to enrich prospect data.

    This task visits the prospect's source_url to extract additional information
    like organizer contact details, full description, etc.

    Args:
        prospect_id: The Prospect ID to enrich
        platform: Platform type (eventbrite, meetup, linkedin, twitter, generic)
        use_playwright: Whether to use browser automation (required for JS-heavy sites)

    Returns:
        Dict with enrichment results
    """
    from scraper.services.enrichment import enrich_prospect

    try:
        result = enrich_prospect(prospect_id, platform, use_playwright)

        if result.get("success"):
            logger.info(
                f"Enriched prospect {prospect_id}: updated {len(result.get('updated_fields', []))} fields"
            )
        else:
            logger.warning(
                f"Failed to enrich prospect {prospect_id}: {result.get('error')}"
            )

        return result

    except Exception as exc:
        logger.exception(
            f"Error in enrich_prospect_detail task for prospect {prospect_id}"
        )
        return {"success": False, "prospect_id": prospect_id, "error": str(exc)}


@shared_task
def enrich_prospects_batch_task(
    prospect_ids: list[int] = None,
    platform: str = "generic",
    use_playwright: bool = False,
    delay_seconds: float = 2.0,
    max_prospects: int = 50,
) -> dict:
    """
    Batch enrichment task for multiple prospects.

    Args:
        prospect_ids: Optional list of specific prospect IDs (or None for auto-discovery)
        platform: Platform type for optimized extraction
        use_playwright: Use browser automation
        delay_seconds: Delay between requests to avoid rate limiting
        max_prospects: Maximum number to process in this batch

    Returns:
        Dict with batch results
    """
    from scraper.services.enrichment import enrich_prospects_batch

    try:
        results = enrich_prospects_batch(
            prospect_ids=prospect_ids,
            platform=platform,
            use_playwright=use_playwright,
            delay_seconds=delay_seconds,
            max_prospects=max_prospects,
        )

        logger.info(
            f"Batch enrichment completed: {results['success']} succeeded, "
            f"{results['failed']} failed, {results['skipped']} skipped out of {results['total']}"
        )

        return results

    except Exception as exc:
        logger.exception("Error in enrich_prospects_batch_task")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "error": str(exc)}


@shared_task
def auto_enrich_new_prospects() -> dict:
    """
    Automatically enrich newly scraped prospects that don't have enrichment data.

    This task is meant to run periodically (e.g., every 30 minutes) to enrich
    prospects that were just scraped but lack contact information.

    Set ENRICHMENT_ENABLED=1 to enable automatic enrichment.
    Set ENRICHMENT_BATCH_SIZE to control how many prospects to enrich per run.
    Set ENRICHMENT_DELAY to control delay between requests (default: 2 seconds).

    Returns:
        Dict with enrichment results
    """
    if not _get_bool("ENRICHMENT_ENABLED", default=False):
        logger.debug("Auto-enrichment disabled (ENRICHMENT_ENABLED not set)")
        return {"enriched": 0, "reason": "disabled"}

    batch_size = int(_get_env("ENRICHMENT_BATCH_SIZE", "25") or "25")
    delay = float(_get_env("ENRICHMENT_DELAY", "2.0") or "2.0")

    # Determine if we should use Playwright (for JS-heavy sites)
    # You can make this configurable per-platform
    use_playwright = _get_bool("ENRICHMENT_USE_PLAYWRIGHT", default=False)

    from scraper.services.enrichment import enrich_prospects_batch

    try:
        results = enrich_prospects_batch(
            prospect_ids=None,  # Auto-discover unenriched prospects
            platform="generic",  # Will be detected from source_url
            use_playwright=use_playwright,
            delay_seconds=delay,
            max_prospects=batch_size,
        )

        logger.info(
            f"Auto-enrichment completed: {results['success']} enriched, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )

        return results

    except Exception as exc:
        logger.exception("Error in auto_enrich_new_prospects")
        return {"enriched": 0, "error": str(exc)}
