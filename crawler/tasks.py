"""
Crawler Celery tasks — fully separate from scraper.

Uses CrawlRun for run history (no ScrapeTarget/ScrapeRun).
Config from env: CRAWLER_MAX_DOMAINS_PER_RUN, CRAWLER_MIN_SCORE_THRESHOLD, etc.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from crawler.crawler import crawl_domain
from crawler.discovery import discover_websites, save_discovered_domains
from crawler.models import CrawlRun, CrawlRunStatus, CrawlRunTrigger, CrawlSource, DiscoveredDomain, WebsiteProfile
from crawler.prospect_pipeline import create_or_update_prospect
from crawler.scoring import get_score_label, score_website

logger = logging.getLogger(__name__)


def _get_crawler_config() -> dict[str, Any]:
    """Read crawler run config from environment (no scraper dependency)."""
    return {
        "max_domains_per_run": int(
            os.getenv("CRAWLER_MAX_DOMAINS_PER_RUN", "500") or "500"
        ),
        "min_score_threshold": int(
            os.getenv("CRAWLER_MIN_SCORE_THRESHOLD", "40") or "40"
        ),
        "rate_limit_seconds": float(
            os.getenv("CRAWLER_RATE_LIMIT_SECONDS", "1.5") or "1.5"
        ),
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def discover_websites_task(self) -> dict[str, Any]:
    """
    Run all enabled CrawlSources. Discover domains, enqueue crawl_domain_task for each.
    Creates a CrawlRun (crawler-owned run record), not ScrapeRun.
    """
    config = _get_crawler_config()
    run = CrawlRun.objects.create(
        trigger=CrawlRunTrigger.SCHEDULED,
        status=CrawlRunStatus.RUNNING,
        started_at=timezone.now(),
        task_id=getattr(self.request, "id", "") or "",
        config=config,
    )

    stats: dict[str, Any] = {
        "domains_discovered": 0,
        "domains_crawled": 0,
        "domains_failed": 0,
        "pages_crawled": 0,
        "prospects_created": 0,
        "prospects_updated": 0,
        "high_score_leads": 0,
        "medium_score_leads": 0,
        "services_detected": {},
    }

    max_domains = config.get("max_domains_per_run", 500)

    try:
        sources = list(
            CrawlSource.objects.filter(enabled=True).order_by("priority", "id")
        )
        new_domain_ids: list[int] = []
        for source in sources:
            urls = discover_websites(source.discovery_query, max_results=20)
            created = save_discovered_domains(urls, source=source)
            stats["domains_discovered"] += int(created)

        pending = list(
            DiscoveredDomain.objects.filter(crawl_status="pending")
            .order_by("priority", "first_seen_at")
            .values_list("id", flat=True)[:max_domains]
        )
        new_domain_ids.extend(pending)

        for domain_id in new_domain_ids:
            crawl_domain_task.delay(domain_id=domain_id, run_id=run.id)

        run.domains_queued = len(new_domain_ids)
        run.stats = stats
        run.status = CrawlRunStatus.SUCCESS
        return {"run_id": run.id, "domains_queued": len(new_domain_ids), "stats": stats}
    except Exception as exc:
        logger.exception("discover_websites_task failed: %s", exc)
        run.status = CrawlRunStatus.FAILED
        run.error_text = str(exc)
        run.stats = stats
        raise
    finally:
        run.finished_at = timezone.now()
        run.save()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def crawl_domain_task(self, domain_id: int, run_id: int) -> dict[str, Any]:
    """
    Crawl a single DiscoveredDomain and dispatch analyze_domain_task.
    run_id refers to CrawlRun (crawler app), not ScrapeRun.
    """
    domain_obj = DiscoveredDomain.objects.get(id=domain_id)
    domain_obj.crawl_status = "crawling"
    domain_obj.crawl_attempts = domain_obj.crawl_attempts + 1
    domain_obj.save(update_fields=["crawl_status", "crawl_attempts"])

    try:
        data = crawl_domain(domain_obj)
        domain_obj.crawl_status = "completed" if not data.get("error") else "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = data.get("error") or ""
        domain_obj.save(update_fields=["crawl_status", "last_crawled_at", "error_text"])
        analyze_domain_task.delay(
            domain_id=domain_id, crawl_data=data, run_id=run_id
        )
        return {
            "domain_id": domain_id,
            "pages_crawled": int(data.get("pages_crawled") or 0),
        }
    except Exception as exc:
        logger.exception(
            "crawl_domain_task failed for %s: %s", domain_obj.domain, exc
        )
        domain_obj.crawl_status = "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = str(exc)
        domain_obj.save(update_fields=["crawl_status", "last_crawled_at", "error_text"])
        raise


@shared_task(bind=True, max_retries=2)
def analyze_domain_task(
    self, domain_id: int, crawl_data: dict[str, Any], run_id: int
) -> int:
    """
    Analyze crawl results, build/update WebsiteProfile, dispatch score_and_create_prospect_task.
    run_id is CrawlRun.id.
    """
    from crawler.analyzer import (
        build_international_signals,
        detect_countries,
        detect_languages_from_html,
        detect_org_types,
        detect_services,
    )
    from crawler.extractor import extract_event_names, extract_org_name

    domain_obj = DiscoveredDomain.objects.get(id=domain_id)
    pages = list(crawl_data.get("pages") or [])
    combined_text = "\n".join((p.get("text") or "") for p in pages)
    html_pages = [p.get("html") or "" for p in pages]

    org_types = detect_org_types(combined_text)
    services = detect_services(combined_text)
    countries = detect_countries(combined_text)
    langs = detect_languages_from_html(html_pages)
    signals = build_international_signals(combined_text)
    org_name = extract_org_name(combined_text, domain=domain_obj.domain)
    event_names = extract_event_names(combined_text)

    profile, _ = WebsiteProfile.objects.get_or_create(domain=domain_obj)
    profile.org_name = org_name
    profile.org_type = org_types[0] if org_types else ""
    profile.detected_org_types = org_types
    profile.detected_services = services
    profile.languages_detected = langs
    profile.countries_detected = countries
    profile.international_signals = signals
    profile.event_names = event_names
    profile.contact_emails = list(crawl_data.get("emails") or [])
    profile.contact_phones = list(crawl_data.get("phones") or [])
    profile.pages_crawled = int(crawl_data.get("pages_crawled") or 0)
    profile.save()

    score_and_create_prospect_task.delay(domain_id=domain_id, run_id=run_id)
    return profile.id


@shared_task(bind=True)
def score_and_create_prospect_task(
    self, domain_id: int, run_id: int
) -> dict[str, Any]:
    """
    Score WebsiteProfile; if above threshold, create/update Prospect.
    Updates CrawlRun stats (prospects_created/updated, etc.). run_id is CrawlRun.id.
    """
    profile = WebsiteProfile.objects.select_related("domain").get(
        domain_id=domain_id
    )
    score = score_website(profile)
    profile.translation_need_score = score
    profile.save(update_fields=["translation_need_score", "analyzed_at"])

    label = get_score_label(score)
    config = _get_crawler_config()
    min_score = config.get("min_score_threshold", 40)

    created = False
    updated = False
    services_counter = Counter(profile.detected_services or [])

    if score > min_score:
        prospect, is_created = create_or_update_prospect(profile, score)
        created = bool(is_created)
        updated = not created
        logger.info(
            "Prospect %s for %s (%s): score=%s",
            prospect.id,
            profile.domain.domain,
            label,
            score,
        )

    try:
        with transaction.atomic():
            run = CrawlRun.objects.select_for_update().get(id=run_id)
            stats = dict(run.stats or {})
            stats["domains_crawled"] = int(stats.get("domains_crawled") or 0) + 1
            stats["pages_crawled"] = int(stats.get("pages_crawled") or 0) + int(
                profile.pages_crawled or 0
            )
            if created:
                stats["prospects_created"] = (
                    int(stats.get("prospects_created") or 0) + 1
                )
                run.prospects_created = int(run.prospects_created or 0) + 1
            if updated:
                stats["prospects_updated"] = (
                    int(stats.get("prospects_updated") or 0) + 1
                )
                run.prospects_updated = int(run.prospects_updated or 0) + 1
            if label == "high":
                stats["high_score_leads"] = (
                    int(stats.get("high_score_leads") or 0) + 1
                )
            if label == "medium":
                stats["medium_score_leads"] = (
                    int(stats.get("medium_score_leads") or 0) + 1
                )
            svc = dict(stats.get("services_detected") or {})
            for k, v in services_counter.items():
                svc[k] = int(svc.get(k) or 0) + int(v)
            stats["services_detected"] = svc
            run.stats = stats
            run.save(
                update_fields=[
                    "stats",
                    "prospects_created",
                    "prospects_updated",
                ]
            )
    except Exception:
        logger.debug(
            "Failed to update CrawlRun stats for run_id=%s", run_id, exc_info=True
        )

    return {"domain_id": domain_id, "score": score, "label": label, "created": created}
