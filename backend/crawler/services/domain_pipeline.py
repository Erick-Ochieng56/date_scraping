from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.utils import timezone

from crawler.models import CrawlRun, CrawlRunDomainResult, DiscoveredDomain, WebsiteProfile
from crawler.services.competitor_filter import is_likely_competitor
from crawler.services.event_processor import process_event_domain
from crawler.services.gemini_analyzer import analyze_domain_safe

logger = logging.getLogger(__name__)


def _gemini_enabled() -> bool:
    return bool(getattr(settings, "GEMINI_API_KEY", None) or "")


def mark_competitor_result(
    result: CrawlRunDomainResult,
    profile: WebsiteProfile,
    reason: str,
    *,
    pages_crawled: int = 0,
) -> None:
    result.is_competitor = True
    result.is_competitor_reason = (reason or "")[:500]
    result.score = 0
    result.score_label = "competitor"
    result.state = "scored"
    result.prospect_created = False
    result.prospect_updated = False
    result.processed_at = timezone.now()
    if pages_crawled:
        result.pages_crawled = pages_crawled
    result.save()

    profile.is_competitor = True
    profile.is_competitor_reason = (reason or "")[:500]
    profile.translation_need_score = 0
    profile.gemini_translation_need_score = None
    profile.excluded_at = timezone.now()
    profile.save(
        update_fields=[
            "is_competitor",
            "is_competitor_reason",
            "translation_need_score",
            "gemini_translation_need_score",
            "excluded_at",
            "analyzed_at",
        ]
    )


def apply_gemini_analysis_to_profile(
    profile: WebsiteProfile,
    analysis: dict[str, Any],
    *,
    merge_emails: list[str],
    merge_phones: list[str],
) -> None:
    """Merge Gemini JSON into WebsiteProfile (non-competitor path)."""
    emails = list(analysis.get("contact_emails") or [])
    phones = list(analysis.get("contact_phones") or [])
    profile.org_name = (analysis.get("org_name") or profile.org_name)[:255]
    profile.org_type = (analysis.get("org_type") or profile.org_type)[:100]
    profile.detected_org_types = analysis.get("detected_org_types") or profile.detected_org_types
    profile.detected_services = analysis.get("detected_services") or profile.detected_services
    profile.languages_detected = analysis.get("languages_detected") or profile.languages_detected
    profile.countries_detected = analysis.get("countries_detected") or profile.countries_detected
    profile.international_signals = analysis.get("international_signals") or profile.international_signals
    if merge_emails:
        seen = {e.lower() for e in emails}
        for e in merge_emails:
            if e and e.lower() not in seen:
                emails.append(e)
                seen.add(e.lower())
    if merge_phones:
        seen_p = set(phones)
        for p in merge_phones:
            if p and p not in seen_p:
                phones.append(p)
                seen_p.add(p)
    profile.contact_emails = emails
    profile.contact_phones = phones
    score = int(analysis.get("translation_need_score") or 0)
    profile.gemini_translation_need_score = score
    profile.is_competitor = False
    profile.is_competitor_reason = ""
    profile.excluded_at = None
    profile.save()


def run_post_analyzer_ai_pipeline(
    crawl_run: CrawlRun,
    discovered_domain: DiscoveredDomain,
    page_url_text_pairs: list[tuple[str, str]],
    profile: WebsiteProfile,
    *,
    run_id: int,
    pages_crawled: int,
    crawl_emails: list[str],
    crawl_phones: list[str],
) -> None:
    """
    Competitor filter → optional events (Gemini) → Gemini domain analysis.
    Mutates ``profile`` and ``CrawlRunDomainResult`` for competitor paths;
    merges Gemini fields into ``profile`` when the API key is set.
    """
    result = CrawlRunDomainResult.objects.get(crawl_run_id=run_id, domain=discovered_domain)
    crawl_source = discovered_domain.source

    page_texts = [t for _, t in page_url_text_pairs]
    flagged, reason = is_likely_competitor(
        discovered_domain.domain,
        page_texts,
        crawl_source=crawl_source,
        org_type_hint=profile.org_type or "",
    )
    if flagged:
        mark_competitor_result(result, profile, reason, pages_crawled=pages_crawled)
        CrawlRunDomainResult.objects.filter(pk=result.pk).update(
            org_name=profile.org_name,
            org_type=profile.org_type,
            detected_org_types=profile.detected_org_types,
            detected_services=profile.detected_services,
            languages_detected=profile.languages_detected,
            countries_detected=profile.countries_detected,
            international_signals=profile.international_signals,
            event_names=profile.event_names,
            contact_emails=profile.contact_emails,
            contact_phones=profile.contact_phones,
        )
        return

    if _gemini_enabled():
        try:
            process_event_domain(crawl_run, discovered_domain, page_url_text_pairs)
        except Exception:
            logger.exception("process_event_domain failed")

        analysis = analyze_domain_safe(discovered_domain.domain, page_texts)
        if analysis.get("is_competitor"):
            mark_competitor_result(
                result,
                profile,
                str(analysis.get("is_competitor_reason") or "Flagged by AI"),
                pages_crawled=pages_crawled,
            )
            CrawlRunDomainResult.objects.filter(pk=result.pk).update(
                org_name=profile.org_name,
                org_type=profile.org_type,
            )
            return

        apply_gemini_analysis_to_profile(
            profile,
            analysis,
            merge_emails=crawl_emails,
            merge_phones=crawl_phones,
        )
