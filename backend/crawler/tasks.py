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

from celery import current_app, shared_task
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


def _run_is_stopped(run_id: int) -> bool:
    run = CrawlRun.objects.filter(id=run_id).only("status", "ends_at").first()
    if not run:
        return True
    if run.status != CrawlRunStatus.RUNNING:
        return True
    if run.ends_at and timezone.now() >= run.ends_at:
        return True
    return False


def _run_is_cancelled(run_id: int) -> bool:
    return _run_is_stopped(run_id)


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


def _get_session_config() -> dict[str, Any]:
    """Crawl session caps layered on top of base crawler config."""
    return {
        **_get_crawler_config(),
        "max_domains_per_cycle": int(
            os.getenv("CRAWLER_SESSION_MAX_DOMAINS_PER_CYCLE", "50") or "50"
        ),
        "cycle_interval_seconds": int(
            os.getenv("CRAWLER_SESSION_CYCLE_INTERVAL_SECONDS", "600") or "600"
        ),
    }


def _default_cycle_stats() -> dict[str, Any]:
    return {
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


def run_discovery_cycle(
    run: CrawlRun,
    *,
    initiated_by_id: int | None = None,
    max_domains: int | None = None,
) -> dict[str, Any]:
    """
    One discovery burst + enqueue pending domains for an existing CrawlRun.
    Used by one-shot discovery and session coordinator cycles.
    """
    config = dict(run.config or _get_crawler_config())
    if max_domains is None:
        max_domains = int(config.get("max_domains_per_run", 500))

    stats = dict(run.stats or _default_cycle_stats())
    for key, default in _default_cycle_stats().items():
        stats.setdefault(key, default if not isinstance(default, dict) else dict(default))

    from crawler.services.prospect_verify import filter_discovery_hit

    sources_qs = CrawlSource.objects.filter(enabled=True)
    if initiated_by_id:
        sources_qs = sources_qs.filter(owner_id=initiated_by_id)
    sources = list(sources_qs.order_by("priority", "id"))

    domain_ids: list[int] = []
    for source in sources:
        if _run_is_stopped(run.id):
            break
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
        created = save_discovered_domains(
            filtered_hits, source=source, owner_id=initiated_by_id
        )
        stats["domains_discovered"] = int(stats.get("domains_discovered") or 0) + int(created)

    pending_qs = DiscoveredDomain.objects.filter(crawl_status="pending")
    if initiated_by_id:
        pending_qs = pending_qs.filter(owner_id=initiated_by_id)
    pending = list(
        pending_qs.order_by("priority", "first_seen_at").values_list("id", flat=True)[
            :max_domains
        ]
    )
    domain_ids.extend(pending)

    enqueued = 0
    for domain_id in domain_ids:
        if _run_is_stopped(run.id):
            break
        CrawlRunDomainResult.objects.get_or_create(
            crawl_run_id=run.id,
            domain_id=domain_id,
            defaults={"state": "queued"},
        )
        crawl_domain_task.delay(
            domain_id=domain_id, run_id=run.id, owner_id=initiated_by_id
        )
        enqueued += 1

    run.domains_queued = int(run.domains_queued or 0) + enqueued
    run.stats = stats
    run.save(update_fields=["domains_queued", "stats"])

    return {"domains_enqueued": enqueued, "stats": stats}


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
        stats=_default_cycle_stats(),
    )

    try:
        result = run_discovery_cycle(
            run,
            initiated_by_id=initiated_by_id,
            max_domains=config.get("max_domains_per_run", 500),
        )
        run.refresh_from_db()
        run.status = CrawlRunStatus.SUCCESS
        return {
            "run_id": run.id,
            "domains_queued": result["domains_enqueued"],
            "stats": result["stats"],
        }
    except Exception as exc:
        logger.exception("discover_websites_task failed: %s", exc)
        run.status = CrawlRunStatus.FAILED
        run.error_text = str(exc)
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


def _maybe_notify_session_progress(run: CrawlRun) -> None:
    """Periodic summary for long sessions (default: every 2h when duration >= 6h)."""
    from dashboard.utils import notify_crawl_session

    duration = int(run.duration_minutes or 0)
    min_duration = int(os.getenv("CRAWLER_SESSION_PROGRESS_MIN_DURATION_MINUTES", "360") or "360")
    if duration < min_duration:
        return

    interval_min = int(os.getenv("CRAWLER_SESSION_PROGRESS_NOTIFY_MINUTES", "120") or "120")
    now = timezone.now()
    stats = dict(run.stats or {})
    last_raw = stats.get("last_progress_notification_at")
    if last_raw:
        try:
            from django.utils.dateparse import parse_datetime

            last_at = parse_datetime(str(last_raw))
            if last_at and timezone.is_naive(last_at):
                last_at = timezone.make_aware(last_at)
        except Exception:
            last_at = None
    else:
        last_at = run.started_at

    if not last_at:
        return
    elapsed_min = (now - last_at).total_seconds() / 60
    if elapsed_min < interval_min:
        return

    if run.owner_id:
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.filter(id=run.owner_id).first()
        if owner:
            notify_crawl_session(owner, run, "progress")

    stats["last_progress_notification_at"] = now.isoformat()
    run.stats = stats
    run.save(update_fields=["stats"])


@shared_task
def enqueue_due_crawl_schedules() -> dict[str, int]:
    """
    Start crawl sessions for enabled schedules whose interval has elapsed.
    Skips owners who already have an active session.
    """
    from django.db import transaction

    from crawler.models import CrawlSchedule
    from crawler.services.crawl_session import (
        SessionStartError,
        default_schedule_session_minutes,
        start_crawl_session_for_user,
        user_has_active_crawl_session,
    )

    now = timezone.now()
    started = 0
    skipped = 0

    schedule_ids = list(
        CrawlSchedule.objects.filter(enabled=True).values_list("id", flat=True)
    )
    for schedule_id in schedule_ids:
        with transaction.atomic():
            schedule = (
                CrawlSchedule.objects.select_for_update()
                .select_related("owner")
                .filter(id=schedule_id, enabled=True)
                .first()
            )
            if not schedule or not schedule.owner_id:
                skipped += 1
                continue

            if user_has_active_crawl_session(schedule.owner_id):
                skipped += 1
                continue

            if schedule.last_started_at:
                elapsed_min = (now - schedule.last_started_at).total_seconds() / 60
                if elapsed_min < schedule.interval_minutes:
                    skipped += 1
                    continue

            duration = schedule.session_duration_minutes or default_schedule_session_minutes()
            try:
                start_crawl_session_for_user(
                    schedule.owner,
                    duration,
                    notify=True,
                )
            except SessionStartError:
                skipped += 1
                continue

            schedule.last_started_at = now
            schedule.save(update_fields=["last_started_at", "updated_at"])
            started += 1

    return {"started": started, "skipped": skipped}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def crawl_session_coordinator_task(self, run_id: int) -> dict[str, Any]:
    """
    Session loop: discovery cycle + domain enqueue until ends_at or cancel.
    Re-queues itself with countdown between cycles.
    """
    run = CrawlRun.objects.filter(id=run_id).first()
    if not run or run.trigger != CrawlRunTrigger.SESSION:
        return {"run_id": run_id, "skipped": "not_session"}
    if _run_is_stopped(run_id):
        return {"run_id": run_id, "skipped": "stopped"}

    config = dict(run.config or _get_session_config())
    max_per_cycle = int(config.get("max_domains_per_cycle", 50))
    cycle_interval = int(config.get("cycle_interval_seconds", 600))

    try:
        result = run_discovery_cycle(
            run,
            initiated_by_id=run.owner_id,
            max_domains=max_per_cycle,
        )
        run.refresh_from_db()
        run.cycles_completed = int(run.cycles_completed or 0) + 1
        run.last_cycle_at = timezone.now()
        run.coordinator_task_id = getattr(self.request, "id", "") or ""
        run.save(
            update_fields=["cycles_completed", "last_cycle_at", "coordinator_task_id"]
        )

        _maybe_notify_session_progress(run)

        if run.ends_at and timezone.now() >= run.ends_at:
            finalize_crawl_session.delay(run_id, reason="deadline")
            return {
                "run_id": run_id,
                "cycle": run.cycles_completed,
                "domains_enqueued": result["domains_enqueued"],
                "finalizing": "deadline",
            }

        crawl_session_coordinator_task.apply_async(
            args=[run_id],
            countdown=cycle_interval,
        )
        return {
            "run_id": run_id,
            "cycle": run.cycles_completed,
            "domains_enqueued": result["domains_enqueued"],
        }
    except Exception as exc:
        logger.exception("crawl_session_coordinator_task failed run_id=%s: %s", run_id, exc)
        finalize_crawl_session.delay(run_id, reason="failed", error=str(exc))
        raise


@shared_task
def finalize_crawl_session(
    run_id: int, reason: str = "completed", error: str = ""
) -> dict[str, Any]:
    """Mark a crawl session finished and notify the initiating user."""
    from dashboard.utils import notify_crawl_session

    with transaction.atomic():
        run = CrawlRun.objects.select_for_update().filter(id=run_id).first()
        if not run or run.status != CrawlRunStatus.RUNNING:
            return {"run_id": run_id, "skipped": True}

        if run.coordinator_task_id:
            try:
                current_app.control.revoke(run.coordinator_task_id, terminate=False)
            except Exception:
                pass

        run.finished_at = timezone.now()
        if reason in ("cancelled",):
            run.status = CrawlRunStatus.FAILED
            if not run.error_text:
                run.error_text = "Cancelled by user."
        elif reason == "failed":
            run.status = CrawlRunStatus.FAILED
            run.error_text = (error or "Session failed.")[:2000]
        else:
            run.status = CrawlRunStatus.SUCCESS
            if reason == "deadline":
                run.error_text = ""
        run.save(update_fields=["status", "error_text", "finished_at"])

    if run.owner_id:
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.filter(id=run.owner_id).first()
        if owner:
            notify_crawl_session(owner, run, reason)

    return {"run_id": run_id, "reason": reason, "status": run.status}


@shared_task
def sweep_expired_crawl_sessions() -> dict[str, Any]:
    """Backup finalizer for sessions whose ETA finalize was missed."""
    now = timezone.now()
    expired = list(
        CrawlRun.objects.filter(
            status=CrawlRunStatus.RUNNING,
            trigger=CrawlRunTrigger.SESSION,
            ends_at__lte=now,
        ).values_list("id", flat=True)
    )
    for run_id in expired:
        finalize_crawl_session.delay(run_id, reason="deadline")
    return {"finalized": len(expired)}


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
