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
from urllib.parse import urlparse

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone

from crawler.crawler import crawl_domain
from crawler.discovery import (
    coerce_discovery_hit,
    discover_websites,
    save_discovered_domains,
    should_replace_source_url,
)
from crawler.utils import normalize_url
from crawler.models import (
    CrawlRun,
    CrawlRunDomainResult,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSource,
    DiscoveredDomain,
    WebsiteProfile,
)
from crawler.prospect_pipeline import create_or_update_prospect
from crawler.scoring import get_score_label, score_website
from crawler.services.domain_pipeline import run_post_analyzer_ai_pipeline

logger = logging.getLogger(__name__)


def _run_is_cancelled(run_id: int) -> bool:
    run = CrawlRun.objects.filter(id=run_id).only("status").first()
    return bool(run and run.status != CrawlRunStatus.RUNNING)


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
def discover_websites_task(self, initiated_by_id: int | None = None) -> dict[str, Any]:
    """
    Run all enabled CrawlSources. Discover domains, enqueue crawl_domain_task for each.
    Creates a CrawlRun (crawler-owned run record), not ScrapeRun.
    """
    config = _get_crawler_config()
    run = CrawlRun.objects.create(
        owner_id=initiated_by_id,
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
        sources_qs = CrawlSource.objects.filter(enabled=True)
        if initiated_by_id:
            sources_qs = sources_qs.filter(owner_id=initiated_by_id)
        sources = list(sources_qs.order_by("priority", "id"))
        new_domain_ids: list[int] = []
        from crawler.services.prospect_verify import filter_discovery_hit

        for source in sources:
            hits = discover_websites(source.discovery_query, max_results=20)
            filtered_hits = []
            for hit in hits:
                ok, reason = filter_discovery_hit(
                    hit,
                    source,
                    seed_topic=(source.discovery_query or ""),
                )
                if not ok:
                    logger.info(
                        "Discovery dropped %s: %s",
                        hit.get("domain", ""),
                        reason,
                    )
                    continue
                filtered_hits.append(hit)
            created = save_discovered_domains(filtered_hits, source=source, owner_id=initiated_by_id)
            stats["domains_discovered"] += int(created)

        pending_qs = DiscoveredDomain.objects.filter(crawl_status="pending")
        if initiated_by_id:
            pending_qs = pending_qs.filter(owner_id=initiated_by_id)
        pending = list(
            pending_qs
            .order_by("priority", "first_seen_at")
            .values_list("id", flat=True)[:max_domains]
        )
        new_domain_ids.extend(pending)

        for domain_id in new_domain_ids:
            CrawlRunDomainResult.objects.get_or_create(
                crawl_run_id=run.id,
                domain_id=domain_id,
                defaults={"state": "queued"},
            )
            crawl_domain_task.delay(domain_id=domain_id, run_id=run.id, owner_id=initiated_by_id)

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
def crawl_domain_task(self, domain_id: int, run_id: int, owner_id: int | None = None) -> dict[str, Any]:
    """
    Crawl a single DiscoveredDomain and dispatch analyze_domain_task.
    run_id refers to CrawlRun (crawler app), not ScrapeRun.
    """
    if _run_is_cancelled(run_id):
        return {"domain_id": domain_id, "skipped": "run_not_running"}

    domain_obj = DiscoveredDomain.objects.get(id=domain_id)
    # Manual crawl triggers (staff/admin API) create a CrawlRun but did not create a
    # ledger row; discover_websites_task does. Keep analyze_domain_task / pipeline safe.
    CrawlRunDomainResult.objects.get_or_create(
        crawl_run_id=run_id,
        domain_id=domain_id,
        defaults={"state": "queued"},
    )
    domain_obj.crawl_status = "crawling"
    domain_obj.crawl_attempts = domain_obj.crawl_attempts + 1
    domain_obj.save(update_fields=["crawl_status", "crawl_attempts"])

    try:
        data = crawl_domain(domain_obj)
        domain_obj.crawl_status = "completed" if not data.get("error") else "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = data.get("error") or ""
        domain_obj.save(update_fields=["crawl_status", "last_crawled_at", "error_text"])
        pages = int(data.get("pages_crawled") or 0)
        CrawlRunDomainResult.objects.filter(
            crawl_run_id=run_id, domain_id=domain_id
        ).update(
            state="crawled",
            crawl_succeeded=not data.get("error"),
            crawl_error=data.get("error") or "",
            pages_crawled=pages,
        )
        analyze_domain_task.delay(
            domain_id=domain_id, crawl_data=data, run_id=run_id, owner_id=owner_id
        )
        return {
            "domain_id": domain_id,
            "pages_crawled": pages,
        }
    except Exception as exc:
        logger.exception(
            "crawl_domain_task failed for %s: %s", domain_obj.domain, exc
        )
        domain_obj.crawl_status = "failed"
        domain_obj.last_crawled_at = timezone.now()
        domain_obj.error_text = str(exc)
        domain_obj.save(update_fields=["crawl_status", "last_crawled_at", "error_text"])
        CrawlRunDomainResult.objects.filter(
            crawl_run_id=run_id, domain_id=domain_id
        ).update(state="failed", crawl_succeeded=False, crawl_error=str(exc))
        raise


@shared_task(bind=True, max_retries=2)
def analyze_domain_task(
    self, domain_id: int, crawl_data: dict[str, Any], run_id: int, owner_id: int | None = None
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

    if _run_is_cancelled(run_id):
        return 0

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

    page_url_text_pairs = [
        ((p.get("url") or "").strip(), (p.get("text") or "").strip()) for p in pages
    ]
    crawl_run = CrawlRun.objects.get(pk=run_id)
    run_post_analyzer_ai_pipeline(
        crawl_run,
        domain_obj,
        page_url_text_pairs,
        profile,
        run_id=run_id,
        pages_crawled=int(crawl_data.get("pages_crawled") or 0),
        crawl_emails=list(crawl_data.get("emails") or []),
        crawl_phones=list(crawl_data.get("phones") or []),
    )
    profile.refresh_from_db()

    result_update = {
        "org_name": profile.org_name or "",
        "org_type": profile.org_type or "",
        "detected_org_types": profile.detected_org_types or [],
        "detected_services": profile.detected_services or [],
        "languages_detected": profile.languages_detected or [],
        "countries_detected": profile.countries_detected or [],
        "international_signals": profile.international_signals or [],
        "event_names": profile.event_names or [],
        "contact_emails": profile.contact_emails or [],
        "contact_phones": profile.contact_phones or [],
    }
    if profile.is_competitor:
        result_update.update(
            {
                "state": "scored",
                "score": 0,
                "score_label": "competitor",
                "is_competitor": True,
                "is_competitor_reason": (profile.is_competitor_reason or "")[:500],
                "prospect_created": False,
                "prospect_updated": False,
                "processed_at": timezone.now(),
            }
        )
    else:
        result_update["state"] = "analyzed"

    CrawlRunDomainResult.objects.filter(
        crawl_run_id=run_id, domain_id=domain_id
    ).update(**result_update)

    score_and_create_prospect_task.delay(domain_id=domain_id, run_id=run_id, owner_id=owner_id)
    return profile.id


@shared_task(bind=True)
def score_and_create_prospect_task(
    self, domain_id: int, run_id: int, owner_id: int | None = None
) -> dict[str, Any]:
    """
    Score WebsiteProfile; if above threshold, create/update Prospect.
    Updates CrawlRun stats (prospects_created/updated, etc.). run_id is CrawlRun.id.
    """
    if _run_is_cancelled(run_id):
        return {"domain_id": domain_id, "skipped": "run_not_running"}

    profile = WebsiteProfile.objects.select_related("domain").get(
        domain_id=domain_id
    )

    if profile.is_competitor:
        CrawlRunDomainResult.objects.filter(
            crawl_run_id=run_id, domain_id=domain_id
        ).update(
            state="scored",
            score=0,
            score_label="competitor",
            is_competitor=True,
            is_competitor_reason=(profile.is_competitor_reason or "")[:500],
            prospect_created=False,
            prospect_updated=False,
            processed_at=timezone.now(),
        )
        _increment_crawl_run_domain_stats(
            run_id,
            profile,
            created=False,
            updated=False,
            label="low",
            services_counter=Counter(),
        )
        return {
            "domain_id": domain_id,
            "score": 0,
            "label": "competitor",
            "created": False,
            "skipped": "competitor",
        }

    if profile.gemini_translation_need_score is not None:
        score = int(profile.gemini_translation_need_score)
    else:
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
        prospect, is_created = create_or_update_prospect(profile, score, owner_id=owner_id)
        created = bool(is_created)
        updated = not created
        logger.info(
            "Prospect %s for %s (%s): score=%s",
            prospect.id,
            profile.domain.domain,
            label,
            score,
        )
    else:
        created = False
        updated = False

    CrawlRunDomainResult.objects.filter(
        crawl_run_id=run_id, domain_id=domain_id
    ).update(
        state="scored",
        score=score,
        score_label=label,
        is_competitor=False,
        is_competitor_reason="",
        prospect_created=created,
        prospect_updated=updated,
        processed_at=timezone.now(),
    )

    _increment_crawl_run_domain_stats(
        run_id,
        profile,
        created=created,
        updated=updated,
        label=label,
        services_counter=services_counter,
    )

    return {"domain_id": domain_id, "score": score, "label": label, "created": created}


def _increment_crawl_run_domain_stats(
    run_id: int,
    profile: WebsiteProfile,
    *,
    created: bool,
    updated: bool,
    label: str,
    services_counter: Counter,
) -> None:
    try:
        with transaction.atomic():
            run = CrawlRun.objects.select_for_update().get(id=run_id)
            stats = dict(run.stats or {})
            stats["domains_crawled"] = int(stats.get("domains_crawled") or 0) + 1
            stats["pages_crawled"] = int(stats.get("pages_crawled") or 0) + int(
                profile.pages_crawled or 0
            )
            if created:
                stats["prospects_created"] = int(stats.get("prospects_created") or 0) + 1
                run.prospects_created = int(run.prospects_created or 0) + 1
            if updated:
                stats["prospects_updated"] = int(stats.get("prospects_updated") or 0) + 1
                run.prospects_updated = int(run.prospects_updated or 0) + 1
            if label == "high":
                stats["high_score_leads"] = int(stats.get("high_score_leads") or 0) + 1
            if label == "medium":
                stats["medium_score_leads"] = int(stats.get("medium_score_leads") or 0) + 1
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


# Bound wall time: Gemini + many httpx checks can otherwise exceed worker patience and
# leave the UI polling forever without a terminal status.
@shared_task(soft_time_limit=300, time_limit=330)
def run_ai_search_job(job_id: int) -> dict[str, Any]:
    from crawler.models import AISearchJob, AISearchResult, DiscoveredDomain
    from crawler.discovery import _get_serper_api_key
    from crawler.services.ai_search import (
        generate_search_queries,
        grounded_prospect_search,
        serp_company_prospects,
    )
    from crawler.services.ai_page_extract import gemini_extract_enabled, qualify_ai_search_candidate
    from crawler.services.prospect_verify import fetch_page_for_qualification
    from django.conf import settings

    def _record_drop(
        drops: list[dict[str, str]],
        summary: dict[str, int],
        *,
        domain: str,
        url: str,
        reason: str,
    ) -> None:
        reason = (reason or "unknown")[:500]
        drops.append({"domain": domain, "url": url[:500], "reason": reason})
        bucket = reason.split(".")[0][:80] or "unknown"
        summary[bucket] = summary.get(bucket, 0) + 1

    try:
        job = AISearchJob.objects.get(pk=job_id)
        job.status = "generating"
        job.save(update_fields=["status", "updated_at"])

        gemini_on = gemini_extract_enabled()
        serper_on = bool(_get_serper_api_key())
        require_gemini = bool(getattr(settings, "AI_SEARCH_REQUIRE_GEMINI", True))
        logger.info(
            "AI search job %s start: gemini=%s serper=%s require_gemini=%s",
            job_id,
            "on" if gemini_on else "off",
            "on" if serper_on else "off",
            require_gemini,
        )
        if serper_on and not gemini_on:
            logger.warning(
                "AI search job %s: SERPER without GEMINI — page extraction disabled; "
                "qualification uses rules only. Set GEMINI_API_KEY in backend/.env and restart Celery.",
                job_id,
            )
        if require_gemini and not gemini_on:
            job.status = "failed"
            job.error_text = (
                "GEMINI_API_KEY is required for AI search page extraction. "
                "Set it in backend/.env and restart the Celery worker."
            )
            job.save(update_fields=["status", "error_text", "updated_at"])
            return {"job_id": job_id, "error": job.error_text}

        queries = generate_search_queries(
            seed_topic=job.seed_topic,
            industry=job.industry,
            region=job.region,
        )
        job.queries_generated = queries
        job.status = "searching"
        job.save(update_fields=["queries_generated", "status", "updated_at"])

        use_serp_first = serper_on
        if use_serp_first:
            prospects = serp_company_prospects(queries, region=job.region, max_total=45)
        else:
            prospects = []

        if not prospects and gemini_on:
            prospects = grounded_prospect_search(
                topic=job.seed_topic,
                region=job.region,
            )

        if not prospects and not use_serp_first:
            prospects = serp_company_prospects(queries, region=job.region, max_total=45)

        prospects = prospects[:35]
        domains_found = 0
        drops: list[dict[str, str]] = []
        drop_summary: dict[str, int] = {}
        gemini_extracts_left = int(getattr(settings, "AI_SEARCH_MAX_GEMINI_EXTRACTS", 12) or 12)

        for prospect in prospects:
            domain = (prospect.get("domain") or "").strip().lower()
            domain = domain.removeprefix("www.")
            if not domain:
                continue

            raw_src = (
                prospect.get("source_url")
                or prospect.get("landing_url")
                or prospect.get("page_url")
                or ""
            )
            raw_src = (raw_src or "").strip()
            if raw_src and "://" not in raw_src:
                raw_src = "https://" + raw_src.lstrip("/")
            landing = normalize_url(raw_src) if raw_src else ""

            fetch_url = landing or f"https://{domain}"
            fetch_ok, page_text, fetch_reason = fetch_page_for_qualification(
                fetch_url,
                timeout=5.0,
            )
            if not fetch_ok:
                _record_drop(drops, drop_summary, domain=domain, url=fetch_url, reason=fetch_reason)
                logger.info("AI search dropped %s: %s", domain, fetch_reason)
                continue

            verified, verify_reason, enriched = qualify_ai_search_candidate(
                {**prospect, "domain": domain, "source_url": landing or raw_src},
                seed_topic=job.seed_topic,
                page_text=page_text,
                allow_gemini=gemini_extracts_left > 0,
            )
            if gemini_extracts_left > 0 and enriched.get("extraction"):
                gemini_extracts_left -= 1
            if not verified:
                _record_drop(drops, drop_summary, domain=domain, url=fetch_url, reason=verify_reason)
                logger.info("AI search dropped %s: %s", domain, verify_reason)
                continue

            prospect = enriched
            raw_payload = prospect if isinstance(prospect, dict) else {}
            if isinstance(raw_payload, dict):
                raw_payload = {
                    k: v
                    for k, v in raw_payload.items()
                    if k != "extraction"
                }
                if prospect.get("extraction"):
                    raw_payload["extraction"] = prospect["extraction"]

            ai_result = AISearchResult.objects.create(
                job=job,
                domain=domain,
                org_name=prospect.get("org_name", "") or "",
                org_type=prospect.get("org_type", "") or "",
                why_needs_translation=prospect.get("why_needs_translation", "") or "",
                international_signals=prospect.get("international_signals") or [],
                contact_email=prospect.get("contact_email", "") or "",
                raw_data={
                    **raw_payload,
                    "source_url": landing or raw_src,
                    "translation_need_score": prospect.get("translation_need_score"),
                    "evidence_snippet": prospect.get("evidence_snippet", ""),
                    "buyer_signal_type": prospect.get("buyer_signal_type", ""),
                    "action_date": prospect.get("action_date", ""),
                    "action_date_raw": prospect.get("action_date_raw", ""),
                    "has_active_procurement": prospect.get("has_active_procurement"),
                },
            )

            hit = coerce_discovery_hit({"domain": domain, "source_url": landing})
            if not hit:
                continue
            canon = (hit.get("domain") or "").strip()
            if not canon:
                continue
            src = (hit.get("source_url") or canon or "").strip()
            if not src:
                src = f"https://{domain}" if domain else canon
            if src and "://" not in src:
                src = "https://" + src.lstrip("/")
            src = (normalize_url(src) or src).strip() or canon

            discovered, created = DiscoveredDomain.objects.get_or_create(
                domain=canon,
                defaults={
                    "crawl_status": "pending",
                    "priority": 8,
                    "owner": job.owner,
                    "source_url": src,
                },
            )
            if created:
                domains_found += 1
            else:
                upd: list[str] = []
                if should_replace_source_url(discovered.source_url, src, domain_base=canon):
                    discovered.source_url = src
                    upd.append("source_url")
                if not discovered.owner_id and job.owner_id:
                    discovered.owner = job.owner
                    upd.append("owner")
                if upd:
                    discovered.save(update_fields=upd)

            ai_result.queued_domain = discovered
            ai_result.save(update_fields=["queued_domain"])

        job.domains_discovered = domains_found
        job.qualification_log = {
            "providers": {
                "gemini": gemini_on,
                "serper": serper_on,
            },
            "candidates_seen": len(prospects),
            "dropped_count": len(drops),
            "drop_summary": drop_summary,
            "drops": drops[:50],
        }
        job.status = "done"
        job.save(
            update_fields=["domains_discovered", "qualification_log", "status", "updated_at"]
        )
        return {"job_id": job_id, "domains_discovered": domains_found}

    except SoftTimeLimitExceeded:
        try:
            job = AISearchJob.objects.get(pk=job_id)
            job.status = "failed"
            job.error_text = (
                "Timed out after 5 minutes. Start or scale the Celery worker, shorten the seed list, "
                "or reduce network-heavy discovery (fewer SERP queries / domains)."
            )
            job.save(update_fields=["status", "error_text", "updated_at"])
        except Exception:
            logger.exception("Failed to persist AI search job timeout state job_id=%s", job_id)
        raise
    except Exception as e:
        try:
            jb = AISearchJob.objects.get(pk=job_id)
            jb.status = "failed"
            jb.error_text = str(e)[:2000]
            jb.save(update_fields=["status", "error_text", "updated_at"])
        except AISearchJob.DoesNotExist:
            logger.warning("run_ai_search_job: job %s missing while recording failure", job_id)
        raise


@shared_task
def expire_past_events() -> str:
    from datetime import date

    from crawler.models import EventProspect

    expired = EventProspect.objects.filter(
        event_date__lt=date.today(),
        status__in=["new", "qualified"],
    ).update(status="expired")

    return f"Expired {expired} past events"
