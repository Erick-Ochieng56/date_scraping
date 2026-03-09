from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.db import models, transaction
from django.utils import timezone

from crawler.crawler import crawl_domain
from crawler.discovery import discover_websites, save_discovered_domains
from crawler.models import CrawlRunDomainResult, CrawlSource, DiscoveredDomain, WebsiteProfile
from crawler.prospect_pipeline import create_or_update_prospect
from crawler.scoring import get_score_label, score_website

logger = logging.getLogger(__name__)


def _get_or_create_crawler_target():
    """
    Ensure there is a ScrapeTarget representing the crawler.

    Note: We intentionally do NOT introduce a new ScrapeTargetType enum value
    here to avoid modifying existing model definitions. The target is identified
    by name and `config`.
    """
    from scraper.models import ScrapeTarget

    target, _ = ScrapeTarget.objects.get_or_create(
        name="translation_lead_crawler",
        defaults={
            "enabled": True,
            "target_type": "html",
            "start_url": "https://bing.com",
            "run_every_minutes": 720,
            "config": {
                "max_domains_per_run": 500,
                "min_score_threshold": 40,
                "rate_limit_seconds": 1.5,
            },
        },
    )
    return target


def _initial_run_stats() -> dict[str, Any]:
    """
    Build the required ScrapeRun.stats schema with sane defaults.
    """
    from crawler.analyzer import SERVICE_KEYWORDS

    return {
        "domains_discovered": 0,
        "domains_crawled": 0,
        "domains_failed": 0,
        "pages_crawled": 0,
        "prospects_created": 0,
        "prospects_updated": 0,
        "high_score_leads": 0,
        "medium_score_leads": 0,
        "services_detected": {k: 0 for k in SERVICE_KEYWORDS.keys()},
    }


def _extract_title_from_html(html: str) -> str:
    """
    Extract <title> from a small HTML snippet.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html or "", "lxml")
        return (" ".join((soup.title.get_text() if soup.title else "").split()))[:255]
    except Exception:
        return ""


def _compute_next_attempt_at(attempts: int) -> timezone.datetime:
    """
    Exponential backoff for domain crawl retries.

    attempts is the DiscoveredDomain.crawl_attempts value after increment.
    """
    a = max(1, int(attempts or 0))
    # 5m, 10m, 20m, 40m, 80m... capped at 6h
    seconds = min(6 * 60 * 60, (5 * 60) * (2 ** (a - 1)))
    return timezone.now() + timedelta(seconds=seconds)


def _maybe_finalize_run(run_id: int) -> None:
    """
    Finalize ScrapeRun when all queued domains are processed.

    Uses CrawlRunDomainResult as the idempotent source of truth.
    """
    from scraper.models import ScrapeRun, ScrapeRunStatus

    with transaction.atomic():
        run = ScrapeRun.objects.select_for_update().get(id=run_id)
        expected = int(run.item_count or 0)
        if expected <= 0:
            return

        processed = CrawlRunDomainResult.objects.filter(run_id=run_id, processed_at__isnull=False)
        done = processed.count()
        if done < expected:
            return

        # Aggregate run stats from per-domain results
        results = list(processed.only(
            "crawl_succeeded",
            "pages_crawled",
            "prospect_created",
            "prospect_updated",
            "score",
            "score_label",
            "detected_services",
        ))

        stats = _initial_run_stats()
        stats["domains_crawled"] = sum(1 for r in results if r.crawl_succeeded)
        stats["domains_failed"] = sum(1 for r in results if not r.crawl_succeeded)
        stats["pages_crawled"] = sum(int(r.pages_crawled or 0) for r in results)
        stats["prospects_created"] = sum(1 for r in results if r.prospect_created)
        stats["prospects_updated"] = sum(1 for r in results if r.prospect_updated)
        stats["high_score_leads"] = sum(1 for r in results if (r.score_label == "high"))
        stats["medium_score_leads"] = sum(1 for r in results if (r.score_label == "medium"))

        svc_counts: Counter[str] = Counter()
        for r in results:
            for svc in (r.detected_services or []):
                svc_counts[svc] += 1
        stats["services_detected"] = {**stats["services_detected"], **dict(svc_counts)}

        # Preserve discovery count from earlier stage if present
        existing_stats = dict(run.stats or {})
        stats["domains_discovered"] = int(existing_stats.get("domains_discovered") or 0)

        run.stats = stats
        run.created_leads = stats["prospects_created"]
        run.updated_leads = stats["prospects_updated"]
        run.status = ScrapeRunStatus.SUCCESS
        run.finished_at = run.finished_at or timezone.now()
        run.save(
            update_fields=[
                "stats",
                "created_leads",
                "updated_leads",
                "status",
                "finished_at",
                "updated_at",
            ]
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def discover_websites_task(self) -> dict[str, Any]:
    """
    Run all enabled CrawlSources.
    For each source: call discover_websites(query).
    Save domains to DiscoveredDomain queue.
    Dispatch crawl_domain_task for each new domain.
    Update ScrapeRun stats.
    """
    from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeRunTrigger

    target = _get_or_create_crawler_target()
    run = ScrapeRun.objects.create(
        target=target,
        trigger=ScrapeRunTrigger.SCHEDULED,
        status=ScrapeRunStatus.RUNNING,
        started_at=timezone.now(),
    )

    stats: dict[str, Any] = _initial_run_stats()

    max_domains = int((target.config or {}).get("max_domains_per_run") or 500)

    try:
        sources = list(CrawlSource.objects.filter(enabled=True).order_by("priority", "id"))
        new_domain_ids: list[int] = []
        for source in sources:
            urls = discover_websites(source.discovery_query, max_results=20)
            created = save_discovered_domains(urls, source=source)
            stats["domains_discovered"] += int(created)

        # Select pending domains for this run
        now = timezone.now()
        pending = list(
            DiscoveredDomain.objects.filter(crawl_status__in=["pending", "failed"])
            .filter(models.Q(next_attempt_at__isnull=True) | models.Q(next_attempt_at__lte=now))
            .order_by("priority", "first_seen_at")
            .values_list("id", flat=True)[:max_domains]
        )
        new_domain_ids.extend(pending)

        # Record how many domains are expected in this run
        run.item_count = len(new_domain_ids)
        run.stats = stats
        run.save(update_fields=["item_count", "stats", "updated_at"])

        for domain_id in new_domain_ids:
            # Create per-domain ledger row (idempotent)
            CrawlRunDomainResult.objects.get_or_create(
                run_id=run.id,
                domain_id=domain_id,
                defaults={"state": "queued", "processed_at": None},
            )
            crawl_domain_task.delay(domain_id=domain_id, run_id=run.id)

        return {"run_id": run.id, "domains_queued": len(new_domain_ids), "stats": stats}
    except Exception as exc:
        logger.exception("discover_websites_task failed: %s", exc)
        run.status = ScrapeRunStatus.FAILED
        run.error_text = str(exc)
        run.stats = stats
        raise
    finally:
        # Only set finished_at for immediate failure (success is finalized later)
        if run.status == ScrapeRunStatus.FAILED:
            run.finished_at = timezone.now()
        run.save()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def crawl_domain_task(self, domain_id: int, run_id: int) -> dict[str, Any]:
    """
    Crawl a single DiscoveredDomain.
    Call crawl_domain(domain_obj).
    Store results and dispatch analyze_domain_task.
    """
    domain_obj = DiscoveredDomain.objects.get(id=domain_id)
    domain_obj.crawl_status = "crawling"
    domain_obj.crawl_attempts = domain_obj.crawl_attempts + 1
    domain_obj.save(update_fields=["crawl_status", "crawl_attempts"])

    try:
        data = crawl_domain(domain_obj)
        had_error = bool(data.get("error"))
        domain_obj.crawl_status = "completed" if not had_error else "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = data.get("error") or ""
        if had_error:
            domain_obj.next_attempt_at = _compute_next_attempt_at(domain_obj.crawl_attempts)
            domain_obj.save(
                update_fields=[
                    "crawl_status",
                    "last_crawled_at",
                    "error_text",
                    "next_attempt_at",
                ]
            )
        else:
            domain_obj.next_attempt_at = None
            domain_obj.save(
                update_fields=[
                    "crawl_status",
                    "last_crawled_at",
                    "error_text",
                    "next_attempt_at",
                ]
            )

        pages = list(data.get("pages") or [])
        combined_text = "\n".join((p.get("text") or "") for p in pages)
        # Do not ship full HTML through Celery. Keep only small snippets for metadata extraction.
        html_snippets = [(p.get("html") or "")[:8000] for p in pages[:5]]
        page_title = _extract_title_from_html(html_snippets[0] if html_snippets else "")

        compact = {
            "combined_text": combined_text,
            "emails": list(data.get("emails") or []),
            "phones": list(data.get("phones") or []),
            "pages_crawled": int(data.get("pages_crawled") or 0),
            "error": data.get("error"),
            "html_snippets": html_snippets,
            "page_title": page_title,
        }

        # Update per-domain ledger
        CrawlRunDomainResult.objects.update_or_create(
            run_id=run_id,
            domain_id=domain_id,
            defaults={
                "state": "crawled" if not compact.get("error") else "failed",
                "crawl_succeeded": bool(compact.get("pages_crawled")) and not bool(compact.get("error")),
                "crawl_error": compact.get("error") or "",
                "pages_crawled": int(compact.get("pages_crawled") or 0),
                "contact_emails": compact.get("emails") or [],
                "contact_phones": compact.get("phones") or [],
            },
        )

        analyze_domain_task.delay(domain_id=domain_id, crawl_data=compact, run_id=run_id)
        return {"domain_id": domain_id, "pages_crawled": int(compact.get("pages_crawled") or 0)}
    except Exception as exc:
        logger.exception("crawl_domain_task failed for %s: %s", domain_obj.domain, exc)
        domain_obj.crawl_status = "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = str(exc)
        domain_obj.next_attempt_at = _compute_next_attempt_at(domain_obj.crawl_attempts)
        domain_obj.save(
            update_fields=[
                "crawl_status",
                "last_crawled_at",
                "error_text",
                "next_attempt_at",
            ]
        )
        # Retry unless we've exhausted attempts. On terminal failure, mark ledger processed.
        max_r = int(self.max_retries or 0)
        if int(getattr(self.request, "retries", 0)) >= max_r:
            CrawlRunDomainResult.objects.update_or_create(
                run_id=run_id,
                domain_id=domain_id,
                defaults={
                    "state": "failed",
                    "crawl_succeeded": False,
                    "crawl_error": str(exc),
                    "processed_at": timezone.now(),
                },
            )
            _maybe_finalize_run(run_id)
            return {"domain_id": domain_id, "pages_crawled": 0, "error": str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def analyze_domain_task(self, domain_id: int, crawl_data: dict[str, Any], run_id: int) -> int:
    """
    Analyze crawl results.
    Build WebsiteProfile with detected services, org type,
    emails, phones, event names.
    Dispatch score_and_create_prospect_task.
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
    combined_text = (crawl_data.get("combined_text") or "").strip()
    html_snippets = list(crawl_data.get("html_snippets") or [])
    langs = detect_languages_from_html(html_snippets)
    page_title = (crawl_data.get("page_title") or "").strip() or None

    org_types = detect_org_types(combined_text)
    services = detect_services(combined_text)
    countries = detect_countries(combined_text)
    signals = build_international_signals(combined_text)
    org_name = extract_org_name(combined_text, domain=domain_obj.domain, page_title=page_title)
    event_names = extract_event_names(combined_text)

    profile, _ = WebsiteProfile.objects.get_or_create(domain=domain_obj)
    profile.org_name = org_name
    profile.org_type = (org_types[0] if org_types else "")
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

    # Update per-domain ledger with analyzed snapshot
    CrawlRunDomainResult.objects.update_or_create(
        run_id=run_id,
        domain_id=domain_id,
        defaults={
            "state": "analyzed",
            "org_name": org_name,
            "org_type": (org_types[0] if org_types else ""),
            "detected_org_types": org_types,
            "detected_services": services,
            "languages_detected": langs,
            "countries_detected": countries,
            "international_signals": signals,
            "event_names": event_names,
            "contact_emails": list(crawl_data.get("emails") or []),
            "contact_phones": list(crawl_data.get("phones") or []),
        },
    )

    score_and_create_prospect_task.delay(domain_id=domain_id, run_id=run_id)
    return profile.id


@shared_task(bind=True)
def score_and_create_prospect_task(self, domain_id: int, run_id: int) -> dict[str, Any]:
    """
    Score WebsiteProfile.
    If score > 40: call create_or_update_prospect().
    Update ScrapeRun.created_leads or updated_leads counter.
    """
    from scraper.models import ScrapeRun

    profile = WebsiteProfile.objects.select_related("domain").get(domain_id=domain_id)
    score = score_website(profile)
    profile.translation_need_score = score
    profile.save(update_fields=["translation_need_score", "analyzed_at"])

    label = get_score_label(score)

    created = False
    updated = False
    services_counter = Counter(profile.detected_services or [])

    if score > 40:
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

    # Update per-domain ledger and maybe finalize the run (idempotent)
    try:
        CrawlRunDomainResult.objects.update_or_create(
            run_id=run_id,
            domain_id=domain_id,
            defaults={
                "state": "scored",
                "score": score,
                "score_label": label,
                "prospect_created": created,
                "prospect_updated": updated,
                "detected_services": list(profile.detected_services or []),
                "detected_org_types": list(profile.detected_org_types or []),
                "countries_detected": list(profile.countries_detected or []),
                "international_signals": list(profile.international_signals or []),
                "event_names": list(profile.event_names or []),
                "contact_emails": list(profile.contact_emails or []),
                "contact_phones": list(profile.contact_phones or []),
                "pages_crawled": int(profile.pages_crawled or 0),
                "processed_at": timezone.now(),
            },
        )
        _maybe_finalize_run(run_id)
    except Exception:
        logger.debug("Failed to update run ledger/finalize for run_id=%s", run_id, exc_info=True)

    return {"domain_id": domain_id, "score": score, "label": label, "created": created}

