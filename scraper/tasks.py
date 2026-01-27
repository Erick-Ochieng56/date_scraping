from __future__ import annotations

import logging
import os

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeRunTrigger, ScrapeTarget
from scraper.services.runner import run_target
from scraper.services.upsert import upsert_lead_from_item


logger = logging.getLogger(__name__)

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
        items = run_target(target)
        run.item_count = len(items)

        with transaction.atomic():
            for item in items:
                lead, created = upsert_lead_from_item(target=target, item=item)
                if created:
                    created_count += 1
                else:
                    updated_count += 1

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
        logger.exception("Scrape failed for target_id=%s", target_id)
        run.status = ScrapeRunStatus.FAILED
        run.error_text = str(exc)
        raise
    finally:
        run.finished_at = timezone.now()
        run.stats = {
            "created": created_count,
            "updated": updated_count,
        }
        run.save()

