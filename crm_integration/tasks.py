from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from crm_integration.mapping import build_perfex_lead_payload
from crm_integration.models import PerfexLeadSync, PerfexSyncStatus
from crm_integration.perfex_client import PerfexClient, PerfexConfig
from leads.models import Lead, LeadStatus
from scraper.services.hashing import sha256_of_obj


logger = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_bool(name: str, default: bool = False) -> bool:
    v = _get_env(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _client() -> PerfexClient:
    base_url = _get_env("PERFEX_BASE_URL")
    token = _get_env("PERFEX_API_TOKEN")
    timeout = int(_get_env("PERFEX_TIMEOUT_SECONDS", "20") or "20")
    return PerfexClient(PerfexConfig(base_url=base_url or "", token=token or "", timeout_seconds=timeout))


def _perfex_defaults() -> dict:
    """
    Optional defaults for Perfex fields (status/source/assigned etc).
    Provide as JSON in PERFEX_DEFAULTS_JSON.
    """
    raw = _get_env("PERFEX_DEFAULTS_JSON", "") or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


@shared_task
def sync_pending_to_perfex(limit: int = 100) -> int:
    """
    Periodic entrypoint: enqueue sync tasks for pending/error leads due for retry.
    """
    # DISABLED by default - enable only when API key is available
    if not _get_bool("PERFEX_SYNC_ENABLED", default=False):
        return 0

    now = timezone.now()
    qs = (
        PerfexLeadSync.objects.select_related("lead")
        .filter(status__in=[PerfexSyncStatus.PENDING, PerfexSyncStatus.ERROR])
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now))
    )

    ids = list(qs.order_by("next_retry_at", "id").values_list("lead_id", flat=True)[:limit])
    for lead_id in ids:
        sync_lead_to_perfex.delay(lead_id=lead_id)
    return len(ids)


@shared_task(bind=True, max_retries=8)
def sync_lead_to_perfex(self, lead_id: int, force: bool = False) -> str:
    # Check if Perfex sync is enabled and configured
    if not _get_bool("PERFEX_SYNC_ENABLED", default=False):
        return "disabled"
    
    base_url = _get_env("PERFEX_BASE_URL")
    if not base_url:
        logger.warning(f"Perfex sync attempted but PERFEX_BASE_URL not configured for lead_id={lead_id}")
        return "not_configured"
    
    lead = Lead.objects.get(id=lead_id)
    sync, _ = PerfexLeadSync.objects.get_or_create(lead=lead)

    defaults = _perfex_defaults()
    payload = build_perfex_lead_payload(lead, defaults=defaults)
    payload_hash = sha256_of_obj(payload)

    if (
        not force
        and sync.status == PerfexSyncStatus.SYNCED
        and sync.payload_hash
        and sync.payload_hash == payload_hash
    ):
        return "skipped"

    try:
        client = _client()

        if sync.perfex_lead_id:
            result = client.update_lead(sync.perfex_lead_id, payload)
        else:
            result = client.create_lead(payload)

        # Try to extract the new id if returned; different modules differ.
        new_id = ""
        if isinstance(result, dict):
            for key in ("id", "lead_id", "data", "result"):
                val = result.get(key)
                if isinstance(val, (str, int)) and str(val).strip():
                    new_id = str(val)
                    break
                if isinstance(val, dict):
                    inner = val.get("id") or val.get("lead_id")
                    if inner:
                        new_id = str(inner)
                        break

        with transaction.atomic():
            sync.status = PerfexSyncStatus.SYNCED
            sync.last_sync_at = timezone.now()
            sync.last_error = ""
            sync.attempts = 0
            sync.next_retry_at = None
            sync.payload_hash = payload_hash
            sync.last_payload = payload
            if new_id:
                sync.perfex_lead_id = new_id
            sync.save()

            lead.status = LeadStatus.SYNCED
            lead.save(update_fields=["status", "updated_at"])

        return "synced"
    except Exception as exc:
        logger.exception("Perfex sync failed lead_id=%s", lead_id)

        # Record error + set retry time, then retry task.
        sync.attempts = (sync.attempts or 0) + 1
        sync.status = PerfexSyncStatus.ERROR
        sync.last_error = str(exc)
        sync.last_payload = payload
        # Exponential backoff capped at 1 hour
        delay_seconds = min(int((2 ** min(sync.attempts, 10)) * 30), 3600)
        sync.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
        sync.save()

        raise self.retry(exc=exc, countdown=delay_seconds)

