"""Shared Serp hit qualification for manual discovery, preview, and crawl queue."""

from __future__ import annotations

import logging
from typing import Any

from crawler.models import CrawlSource
from crawler.services.active_buyer import (
    _host_from,
    crawler_require_active_buyer,
    passes_active_buyer_gate,
    preflight_candidate_page,
    url_looks_stale,
)
from crawler.services.competitor_filter import is_likely_competitor
from crawler.services.directory_filter import is_directory_or_aggregator
from crawler.services.geo_filter import passes_geo_gate
from crawler.services.prospect_verify import fetch_page_for_qualification

logger = logging.getLogger(__name__)


def filter_discovery_hit(
    hit: dict[str, Any],
    crawl_source: CrawlSource | None = None,
    *,
    seed_topic: str = "",
    strict_active_buyer: bool | None = None,
) -> tuple[bool, str]:
    """
    Qualify a Serp discovery hit using the same rules as AI search:
    verifiable portals, current opportunities, geo, competitor, and timeline checks.
    """
    if strict_active_buyer is None:
        strict_active_buyer = crawler_require_active_buyer()

    domain = (hit.get("domain") or "").strip()
    landing = (hit.get("source_url") or domain or "").strip()
    host = _host_from(domain, landing)

    if not landing:
        return False, "Missing landing URL."

    if url_looks_stale(landing):
        return False, "URL points to archived document from a past year."

    fetch_ok, page_text, fetch_reason = fetch_page_for_qualification(landing, timeout=8.0)
    if not fetch_ok:
        return False, fetch_reason

    ok_pre, pre_reason = preflight_candidate_page(landing, page_text, domain=host)
    if not ok_pre:
        return False, pre_reason

    geo_ok, geo_reason = passes_geo_gate(page_text, landing, domain=host)
    if not geo_ok:
        return False, geo_reason

    flagged_dir, dir_reason = is_directory_or_aggregator(
        host,
        url=landing,
        page_text=page_text,
    )
    if flagged_dir:
        return False, dir_reason

    flagged, reason = is_likely_competitor(
        host,
        [page_text, landing, str(hit.get("title", ""))],
        crawl_source=crawl_source,
        landing_url=landing,
    )
    if flagged:
        return False, reason

    if strict_active_buyer:
        ok, why = passes_active_buyer_gate(
            page_text,
            url=landing,
            domain=host,
        )
        if not ok:
            return False, why

    return True, ""


def filter_discovery_hits(
    hits: list[dict[str, Any]],
    crawl_source: CrawlSource | None = None,
    *,
    seed_topic: str = "",
    strict_active_buyer: bool | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (kept_hits, dropped_hits with drop_reason)."""
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for hit in hits:
        ok, reason = filter_discovery_hit(
            hit,
            crawl_source,
            seed_topic=seed_topic,
            strict_active_buyer=strict_active_buyer,
        )
        if ok:
            kept.append(hit)
        else:
            logger.info(
                "Discovery dropped %s: %s",
                hit.get("source_url") or hit.get("domain"),
                reason,
            )
            dropped.append({**hit, "drop_reason": reason})
    return kept, dropped
