"""
Gemini extraction for AI search SERP landing pages.

Serper retrieves URLs; this module qualifies whether the page is a lead-worthy buyer.
"""

from __future__ import annotations

import json
import logging
import textwrap
import time
from typing import Any

from django.conf import settings

from crawler.models import AISearchResult
from crawler.services.active_buyer import (
    best_portal_opportunity_snippet,
    is_procurement_portal_url,
    passes_active_buyer_gate,
    preflight_candidate_page,
)
from crawler.services.gemini_client import generate_text
from crawler.services.prospect_verify import verify_ai_prospect

logger = logging.getLogger(__name__)

EXTRACT_SCHEMA = {
    "org_name": "string — buyer organization name on this page (not a directory brand)",
    "org_type": "string — NGO, law_firm, hospital, government, university, corporate, association, event_organizer, other",
    "buyer_signal_type": "one of: tender, event, hiring, programme, other",
    "action_date": "YYYY-MM-DD — deadline, event start, or closing date if stated, else empty",
    "action_date_raw": "verbatim date/deadline text from page, else empty",
    "is_past_or_closed": "boolean — true if tender/event is closed, archived, or in the past",
    "has_active_procurement": "boolean — true ONLY if page shows an active tender/RFP/hiring/event procurement NOW",
    "evidence_snippet": "verbatim 1-2 sentences proving active translation/interpretation procurement",
    "translation_need_score": "integer 0-100 — buyer likelihood for LSP services",
    "translation_need_reasoning": "1-2 sentences explaining the score",
    "international_signals": ["short evidence strings"],
    "contact_email": "procurement/events/contact email if visible, else empty string",
    "is_competitor": "boolean — true if this site SELLS translation/interpretation services to clients",
    "is_competitor_reason": "string",
    "is_directory": "boolean — true if page is a tender/event listing aggregator, not the buyer org",
    "reject_reason": "string — if score should be 0, explain briefly, else empty",
}

_SYSTEM = textwrap.dedent(
    """
    You qualify B2B leads for a Language Service Provider (translation, localization,
    conference interpretation, sign language interpreting).

    Analyze ONLY the page content provided. The user found this URL via web search.

    CRITICAL: We want organizations ACTIVELY BUYING language services — not institutions
    that merely operate internationally, employ bilingual staff, or have empty portals.

    OFFICIAL PROCUREMENT PORTALS (ministry, NGO, UN agency on their own domain) ARE valid
    when the page lists at least one CURRENT OPEN tender/RFP mentioning translation,
    interpretation, or language services with a future deadline. Ignore past/closed items
    on the same page. Third-party tender aggregators (kenyatenders.com, etc.) are NOT valid.

    SCORING (translation_need_score):
    - 80-100: Active tender/RFP with future deadline, hiring external interpreters, upcoming
      event with interpretation procurement, OR verified portal listing a current
      language-service opportunity.
    - 40-79: Do NOT use this band — score below 40 instead unless 80+ criteria met.
    - 0-39: Org homepage, careers page, portal with only past tenders, empty portal,
      bilingual staff job, institutional description, or speculative future need.

    Set has_active_procurement=true when THIS page shows a specific open opportunity
    (including a current item on an official procurement portal listing).
    Set is_past_or_closed=true for past conferences, closed tenders, archived documents.
    Set is_competitor=true only when the organization SELLS translation/interpretation services.
    Set is_directory=true for Eventbrite, third-party tender aggregators, job boards.

    Return ONLY valid JSON matching the schema.
    """
)


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s[: s.rfind("```")].strip()
    return s


def ai_search_min_score() -> int:
    try:
        return max(0, min(100, int(getattr(settings, "AI_SEARCH_MIN_SCORE", 80))))
    except (TypeError, ValueError):
        return 80


def ai_search_promote_min_score() -> int:
    try:
        return max(0, min(100, int(getattr(settings, "AI_SEARCH_PROMOTE_MIN_SCORE", 80))))
    except (TypeError, ValueError):
        return 80


def ai_search_require_active_buyer() -> bool:
    return bool(getattr(settings, "AI_SEARCH_REQUIRE_ACTIVE_BUYER", True))


def gemini_extract_enabled() -> bool:
    return bool((getattr(settings, "GEMINI_API_KEY", None) or "").strip())


def extract_prospect_from_page(
    domain: str,
    landing_url: str,
    page_text: str,
    *,
    seed_topic: str = "",
) -> dict[str, Any]:
    model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")
    snippet = (page_text or "")[:24_000]
    prompt = f"""{_SYSTEM}

Search seed topic: "{seed_topic}"
Domain: {domain}
Page URL: {landing_url}

Page text:
{snippet}

Expected JSON schema:
{json.dumps(EXTRACT_SCHEMA, indent=2)}

Return the JSON object now:"""

    raw_text = generate_text(model=model_name, prompt=prompt)
    raw = _strip_code_fence(raw_text)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logger.warning("AI page extract JSON parse failed for domain=%s", domain)
        return {}


def extract_prospect_from_page_safe(
    domain: str,
    landing_url: str,
    page_text: str,
    *,
    seed_topic: str = "",
    retries: int = 3,
) -> dict[str, Any]:
    for attempt in range(retries):
        try:
            return extract_prospect_from_page(
                domain,
                landing_url,
                page_text,
                seed_topic=seed_topic,
            )
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                if attempt == retries - 1:
                    logger.warning("Gemini quota exhausted for %s", domain)
                    return {"quota_exhausted": True}
                time.sleep(2**attempt)
                continue
            if attempt == retries - 1:
                logger.exception("extract_prospect_from_page failed for %s", domain)
                return {"quota_exhausted": True, "reject_reason": err[:200]}
            time.sleep(1)
    return {"quota_exhausted": True}


def _int_score(data: dict[str, Any]) -> int:
    try:
        return max(0, min(100, int(data.get("translation_need_score") or 0)))
    except (TypeError, ValueError):
        return 0


def _bool_field(data: dict[str, Any], key: str) -> bool:
    val = data.get(key)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


def merge_extraction_into_prospect(
    prospect: dict[str, Any],
    extraction: dict[str, Any],
) -> dict[str, Any]:
    """Merge Gemini fields into the SERP prospect dict and raw_data payload."""
    score = _int_score(extraction)
    why = (
        (extraction.get("translation_need_reasoning") or "").strip()
        or (extraction.get("evidence_snippet") or "").strip()
        or prospect.get("why_needs_translation")
        or ""
    )
    emails = extraction.get("contact_email") or ""
    if isinstance(emails, list):
        email = (emails[0] if emails else "") or ""
    else:
        email = str(emails).strip()

    action_date = (extraction.get("action_date") or "").strip()[:10]
    action_date_raw = (extraction.get("action_date_raw") or "").strip()[:200]

    merged = {
        **prospect,
        "org_name": (extraction.get("org_name") or prospect.get("org_name") or "").strip()[:255],
        "org_type": (extraction.get("org_type") or prospect.get("org_type") or "")[:120],
        "why_needs_translation": why[:2000],
        "contact_email": email[:255] or prospect.get("contact_email") or "",
        "international_signals": extraction.get("international_signals")
        or prospect.get("international_signals")
        or [],
        "translation_need_score": score,
        "evidence_snippet": (extraction.get("evidence_snippet") or "")[:2000],
        "buyer_signal_type": (extraction.get("buyer_signal_type") or "")[:80],
        "action_date": action_date,
        "action_date_raw": action_date_raw,
        "has_active_procurement": _bool_field(extraction, "has_active_procurement"),
        "is_past_or_closed": _bool_field(extraction, "is_past_or_closed"),
        "extraction": extraction,
    }
    return merged


def _apply_active_buyer_rules(
    prospect: dict[str, Any],
    *,
    page_text: str,
    landing: str,
) -> tuple[bool, str]:
    if not ai_search_require_active_buyer():
        return True, ""

    extraction = prospect.get("extraction") if isinstance(prospect.get("extraction"), dict) else {}
    return passes_active_buyer_gate(
        page_text,
        url=landing,
        domain=str(prospect.get("domain") or ""),
        action_date=str(prospect.get("action_date") or extraction.get("action_date") or ""),
        action_date_raw=str(prospect.get("action_date_raw") or extraction.get("action_date_raw") or ""),
        is_past_or_closed=bool(prospect.get("is_past_or_closed"))
        or _bool_field(extraction, "is_past_or_closed"),
        has_active_procurement=(
            prospect.get("has_active_procurement")
            if prospect.get("has_active_procurement") is not None
            else _bool_field(extraction, "has_active_procurement")
        ),
        buyer_signal_type=str(prospect.get("buyer_signal_type") or ""),
    )


def qualify_ai_search_candidate(
    prospect: dict[str, Any],
    *,
    seed_topic: str = "",
    page_text: str = "",
    allow_gemini: bool = True,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Enrich with Gemini (when configured) and apply rule filters.

    Returns (ok, reason, enriched_prospect).
    """
    domain = (prospect.get("domain") or "").strip()
    landing = (
        prospect.get("source_url")
        or prospect.get("landing_url")
        or prospect.get("page_url")
        or ""
    )

    enriched = dict(prospect)

    ok_pre, pre_reason = preflight_candidate_page(landing, page_text, domain=domain)
    if not ok_pre:
        return False, pre_reason, enriched

    if is_procurement_portal_url(landing):
        snippet = best_portal_opportunity_snippet(page_text)
        if snippet:
            enriched["evidence_snippet"] = snippet
            enriched["buyer_signal_type"] = enriched.get("buyer_signal_type") or "tender"

    extracted = False
    quota_fallback = False

    if gemini_extract_enabled() and allow_gemini and len((page_text or "").strip()) >= 120:
        extraction = extract_prospect_from_page_safe(
            domain,
            landing,
            page_text,
            seed_topic=seed_topic,
        )

        if extraction.get("quota_exhausted"):
            quota_fallback = True
            logger.warning(
                "AI search %s: Gemini unavailable — using rules-only qualification",
                domain,
            )
        else:
            enriched = merge_extraction_into_prospect(enriched, extraction)
            extracted = True

            if extraction.get("is_competitor"):
                reason = (extraction.get("is_competitor_reason") or "Flagged as LSP/competitor").strip()
                return False, reason, enriched

            if extraction.get("is_directory"):
                return False, "Page classified as directory/aggregator by AI", enriched

            reject = (extraction.get("reject_reason") or "").strip()
            score = _int_score(extraction)
            if reject and score < ai_search_min_score():
                return False, reject[:500], enriched

            if score < ai_search_min_score():
                return (
                    False,
                    f"Translation need score {score} below minimum {ai_search_min_score()}",
                    enriched,
                )

            ok, reason = _apply_active_buyer_rules(enriched, page_text=page_text, landing=landing)
            if not ok:
                return False, reason, enriched

    ok, reason = verify_ai_prospect(
        enriched,
        seed_topic=seed_topic,
        page_text=page_text,
        landing_url=landing,
        strict_active_buyer=ai_search_require_active_buyer() and (quota_fallback or not extracted),
    )
    if not ok:
        return False, reason, enriched

    if extracted and _int_score(enriched) < ai_search_min_score():
        return (
            False,
            f"Translation need score {_int_score(enriched)} below minimum {ai_search_min_score()}",
            enriched,
        )

    if ai_search_require_active_buyer() and (quota_fallback or not extracted):
        ok, reason = _apply_active_buyer_rules(enriched, page_text=page_text, landing=landing)
        if not ok:
            return False, reason, enriched

    return True, "", enriched


def result_translation_need_score(result: AISearchResult) -> int | None:
    raw = result.raw_data if isinstance(result.raw_data, dict) else {}
    if "translation_need_score" in raw:
        try:
            return max(0, min(100, int(raw["translation_need_score"])))
        except (TypeError, ValueError):
            pass
    extraction = raw.get("extraction")
    if isinstance(extraction, dict) and "translation_need_score" in extraction:
        try:
            return max(0, min(100, int(extraction["translation_need_score"])))
        except (TypeError, ValueError):
            pass
    return None


def result_action_date(result: AISearchResult) -> str:
    raw = result.raw_data if isinstance(result.raw_data, dict) else {}
    return (raw.get("action_date") or "")[:10]


def result_promotable(result: AISearchResult) -> bool:
    score = result_translation_need_score(result)
    if score is None:
        return False
    return score >= ai_search_promote_min_score()
