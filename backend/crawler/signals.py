from __future__ import annotations

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from crawler.models import CrawlSource

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CrawlSource)
def auto_derive_competitor_signals(sender, instance: CrawlSource, created, **kwargs):
    """Auto-populate competitor_keywords when a CrawlSource has no manual override."""
    if instance.competitor_keywords:
        return
    key = getattr(settings, "GEMINI_API_KEY", None) or ""
    if not key:
        return
    try:
        from crawler.services.competitor_deriver import derive_competitor_signals

        signals = derive_competitor_signals(instance.discovery_query)
    except Exception:
        logger.exception("auto_derive_competitor_signals failed for source_id=%s", instance.pk)
        return

    CrawlSource.objects.filter(pk=instance.pk).update(
        competitor_keywords=signals.get("competitor_keywords", []),
        competitor_org_types=signals.get("competitor_org_types", []),
    )
