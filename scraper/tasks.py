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
from scraper.services.upsert import upsert_lead_from_item


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
    if not _get_bool("PERFEX_SYNC_ENABLED", default=True):
        return
    # Lazy import to avoid cyclic imports at module import time.
    from crm_integration.models import PerfexLeadSync
    from crm_integration.tasks import sync_lead_to_perfex

    PerfexLeadSync.objects.get_or_create(lead_id=lead_id)
    sync_lead_to_perfex.delay(lead_id=lead_id)


def _enqueue_sheets_sync(lead_id: int) -> None:
    if not _get_bool("GSHEETS_ENABLED", default=True):
        return
    from sheets_integration.tasks import append_lead_to_sheet

    append_lead_to_sheet.delay(lead_id=lead_id)


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
                lead, created = upsert_lead_from_item(target=target, item=item)
                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # Primary integration: Google Sheets (always enabled if configured)
                # Leads are reviewed in Sheets, then manually added to CRM
                _enqueue_sheets_sync(lead.id)

                # Perfex CRM sync is DISABLED by default
                # Enable only when API key is available: set PERFEX_SYNC_ENABLED=1
                # For now, leads are manually added to CRM after review in Google Sheets
                _enqueue_perfex_sync(lead.id)

                # Minimal status transitions: keep NEW unless you want auto-review.
                if lead.status not in {"new", "reviewed", "error", "synced"}:
                    lead.status = "new"
                    lead.save(update_fields=["status"])

        run.created_leads = created_count
        run.updated_leads = updated_count
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
            "dns" in error_lower or
            "resolve" in error_lower or
            "getaddrinfo" in error_lower or
            "connection" in error_lower or
            "name_not_resolved" in error_lower or
            "err_name_not_resolved" in error_lower
        )
        
        is_timeout_error = "timeout" in error_lower
        
        is_config_error = (
            "missing" in error_lower and "config" in error_lower or
            "selector" in error_lower or
            "css" in error_lower
        )
        
        # Don't re-raise network/timeout errors - allow other targets to continue
        # But still mark this run as failed
        if is_network_error:
            logger.warning(
                "Target %s failed due to network/DNS issue. Check internet connection. "
                "Error: %s", target_id, error_msg[:200]
            )
            # Don't re-raise - let other targets run
            return 0
        elif is_timeout_error:
            logger.warning(
                "Target %s timed out. Consider increasing timeout_seconds in config. "
                "Error: %s", target_id, error_msg[:200]
            )
            # Don't re-raise - let other targets run
            return 0
        elif is_config_error:
            logger.warning(
                "Target %s has invalid configuration. Disable it or fix the config in admin. "
                "Error: %s", target_id, error_msg[:200]
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
            "message": "Targets synced successfully"
        }
    except Exception as exc:
        logger.exception("Failed to sync targets from config")
        return {
            "synced": 0,
            "error": str(exc),
            "file": str(config_file)
        }

