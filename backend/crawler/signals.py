from __future__ import annotations

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from crawler.models import CrawlSource

logger = logging.getLogger(__name__)


def _is_rate_limited_error(exc: Exception) -> bool:
    err = str(exc)
    return "429" in err or "RESOURCE_EXHAUSTED" in err


@receiver(post_save, sender=CrawlSource)
def auto_derive_competitor_signals(sender, instance: CrawlSource, created, **kwargs):
    """Auto-populate competitor_keywords when a new CrawlSource has no manual override."""
    if not created:
        return
    if not getattr(settings, "CRAWLER_AUTO_DERIVE_COMPETITOR_SIGNALS", True):
        return
    if instance.competitor_keywords:
        return
    key = getattr(settings, "GEMINI_API_KEY", None) or ""
    if not key:
        return
    try:
        from crawler.services.competitor_deriver import derive_competitor_signals

        signals = derive_competitor_signals(instance.discovery_query)
    except Exception as exc:
        if _is_rate_limited_error(exc):
            logger.warning(
                "auto_derive_competitor_signals skipped for source_id=%s (Gemini rate limit)",
                instance.pk,
            )
        else:
            logger.exception("auto_derive_competitor_signals failed for source_id=%s", instance.pk)
        return

    CrawlSource.objects.filter(pk=instance.pk).update(
        competitor_keywords=signals.get("competitor_keywords", []),
        competitor_org_types=signals.get("competitor_org_types", []),
        prospect_org_types=signals.get("prospect_org_types", []),
        prospect_signals=signals.get("prospect_signals", []),
    )


def disconnect_auto_derive_competitor_signals() -> None:
    post_save.disconnect(auto_derive_competitor_signals, sender=CrawlSource)


def connect_auto_derive_competitor_signals() -> None:
    post_save.connect(auto_derive_competitor_signals, sender=CrawlSource)
