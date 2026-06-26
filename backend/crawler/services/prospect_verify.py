from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup

from crawler.models import CrawlSource
from crawler.services.ai_search import text_has_buyer_intent
from crawler.services.competitor_filter import is_likely_competitor
from crawler.services.directory_filter import is_directory_or_aggregator
from crawler.services.geo_filter import passes_geo_gate

logger = logging.getLogger(__name__)

_MAX_FETCH_BYTES = 1_500_000

_PAST_EVENT_PHRASES = (
    "was held",
    "took place",
    "past event",
    "previous edition",
    "last year's",
    "event archive",
    "registration closed",
    "event has ended",
    "concluded on",
)

_FUTURE_EVENT_PHRASES = (
    "upcoming",
    "register now",
    "registration open",
    "will be held",
    "takes place on",
    "join us on",
    "save the date",
)


def _is_pdf_body(body: bytes, content_type: str = "") -> bool:
    if (body[:5] or b"").startswith(b"%PDF"):
        return True
    return "pdf" in (content_type or "").lower()


def fetch_page_for_qualification(
    url: str,
    *,
    timeout: float = 8.0,
    max_bytes: int = _MAX_FETCH_BYTES,
    max_chars: int = 8000,
) -> tuple[bool, str, str]:
    """
    Single HTTP GET for AI search qualification.

    Returns (fetch_ok, page_text, reject_reason). When fetch_ok is False,
    reject_reason explains why the candidate was dropped.
    """
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return False, "", "Invalid URL"
    try:
        with httpx.stream(
            "GET",
            u,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DateScrapingBot/1.0)"},
        ) as resp:
            if resp.status_code >= 500:
                return False, "", f"HTTP {resp.status_code}"
            if resp.status_code >= 400:
                return False, "", f"HTTP {resp.status_code}"

            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total >= max_bytes:
                    break

            body = b"".join(chunks)
            if _is_pdf_body(body, resp.headers.get("content-type") or ""):
                return False, "", "PDF document (skipped)"

            html = body.decode(resp.encoding or "utf-8", errors="replace")
    except Exception as exc:
        logger.debug("fetch_page_for_qualification failed for %s: %s", u, exc)
        return False, "", f"Fetch failed: {exc.__class__.__name__}"

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    return True, text[:max_chars], ""


def fetch_page_text_snippet(url: str, *, timeout: float = 8.0, max_chars: int = 8000) -> str:
    """Fetch a URL and return visible text (best-effort). Empty string on failure."""
    ok, text, _ = fetch_page_for_qualification(
        url,
        timeout=timeout,
        max_chars=max_chars,
    )
    return text if ok else ""


def _meaningful_tokens(text: str, *, min_len: int = 3) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= min_len]


def _token_overlap(page_text: str, reference: str, *, min_hits: int = 2) -> bool:
    ref_tokens = _meaningful_tokens(reference)
    if not ref_tokens:
        return True
    page_low = (page_text or "").lower()
    hits = sum(1 for t in ref_tokens if t in page_low)
    required = min(min_hits, len(ref_tokens))
    return hits >= required


def _page_relates_to_search(
    page_text: str,
    *,
    seed_topic: str = "",
    intent_reference: str = "",
) -> bool:
    if seed_topic and _token_overlap(page_text, seed_topic, min_hits=2):
        return True
    if intent_reference and _token_overlap(page_text, intent_reference, min_hits=2):
        return True
    if text_has_buyer_intent(page_text):
        return True
    combined = f"{seed_topic} {intent_reference}".strip()
    if combined and text_has_buyer_intent(combined) and _token_overlap(page_text, seed_topic, min_hits=1):
        return True
    return False


def _is_event_like_seed(seed: str) -> bool:
    low = (seed or "").lower()
    return any(w in low for w in ("conference", "summit", "event", "forum", "expo", "symposium"))


def _year_tokens_in_text(text: str) -> list[int]:
    return [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")]


def looks_like_past_event_text(event_date_raw: str = "", extra_text: str = "") -> bool:
    combined = f"{event_date_raw} {extra_text}".lower()
    if any(p in combined for p in _PAST_EVENT_PHRASES):
        return True
    years = _year_tokens_in_text(combined)
    if years and max(years) < date.today().year:
        return True
    return False


def page_supports_prospect(
    page_text: str,
    *,
    org_name: str = "",
    seed_topic: str = "",
    intent_reference: str = "",
) -> tuple[bool, str]:
    """
    Basic evidence check: landing page should mention the org and/or search intent.
    """
    text = (page_text or "").strip()
    if len(text) < 120:
        return False, "Landing page has insufficient readable text."

    if org_name and not _token_overlap(text, org_name, min_hits=2):
        return False, f"Page text does not mention organization '{org_name}'."

    if seed_topic and not _page_relates_to_search(
        text,
        seed_topic=seed_topic,
        intent_reference=intent_reference,
    ):
        return False, "Page text does not relate to the search topic."

    if _is_event_like_seed(seed_topic) and looks_like_past_event_text(extra_text=text):
        if not any(p in text.lower() for p in _FUTURE_EVENT_PHRASES):
            return False, "Page appears to describe a past or archived event."

    geo_ok, geo_reason = passes_geo_gate(text, org_name, domain="")
    if not geo_ok:
        return False, geo_reason

    return True, ""


def filter_discovery_hit(
    hit: dict[str, Any],
    crawl_source: CrawlSource | None = None,
    *,
    seed_topic: str = "",
    strict_active_buyer: bool | None = None,
) -> tuple[bool, str]:
    """Delegate to shared discovery qualification (active buyer + timeline rules)."""
    from crawler.services.discovery_qualify import filter_discovery_hit as _filter

    return _filter(
        hit,
        crawl_source,
        seed_topic=seed_topic,
        strict_active_buyer=strict_active_buyer,
    )


def filter_discovery_hits(
    hits: list[dict[str, Any]],
    crawl_source: CrawlSource | None = None,
    *,
    seed_topic: str = "",
    strict_active_buyer: bool | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from crawler.services.discovery_qualify import filter_discovery_hits as _filter_many

    return _filter_many(
        hits,
        crawl_source,
        seed_topic=seed_topic,
        strict_active_buyer=strict_active_buyer,
    )


def verify_ai_prospect(
    prospect: dict[str, Any],
    *,
    seed_topic: str = "",
    crawl_source: CrawlSource | None = None,
    page_text: str | None = None,
    landing_url: str = "",
    strict_active_buyer: bool = False,
) -> tuple[bool, str]:
    """
    Validate grounded/SERP prospect before persisting AISearchResult.
    """
    domain = (prospect.get("domain") or "").strip().lower().removeprefix("www.")
    landing = (landing_url or "").strip() or (
        prospect.get("source_url")
        or prospect.get("landing_url")
        or prospect.get("page_url")
        or ""
    )
    landing = (landing or "").strip()
    if landing and "://" not in landing:
        landing = "https://" + landing.lstrip("/")

    if page_text is None:
        page_text = fetch_page_text_snippet(landing) if landing else ""
        if not page_text and domain:
            page_text = fetch_page_text_snippet(f"https://{domain}")

    intent_reference = str(prospect.get("why_needs_translation", "") or "").strip()

    meta_texts = [
        page_text,
        intent_reference,
        str(prospect.get("org_type", "")),
        str(prospect.get("org_name", "")),
        landing,
    ]
    flagged, reason = is_likely_competitor(
        domain,
        [t for t in meta_texts if t],
        crawl_source=crawl_source,
        org_type_hint=str(prospect.get("org_type", "")),
        landing_url=landing,
    )
    if flagged:
        return False, reason

    ok, why = page_supports_prospect(
        page_text,
        org_name=str(prospect.get("org_name", "")),
        seed_topic=seed_topic,
        intent_reference=intent_reference,
    )
    if not ok:
        score = prospect.get("translation_need_score")
        try:
            score_int = int(score) if score is not None else 0
        except (TypeError, ValueError):
            score_int = 0
        if score_int >= 70:
            pass
        else:
            return False, why

    flagged_dir, dir_reason = is_directory_or_aggregator(
        domain,
        url=landing,
        page_text=page_text,
    )
    if flagged_dir:
        return False, dir_reason

    geo_ok, geo_reason = passes_geo_gate(
        page_text,
        intent_reference,
        landing,
        domain=domain,
    )
    if not geo_ok:
        return False, geo_reason

    if strict_active_buyer:
        from crawler.services.active_buyer import passes_active_buyer_gate

        extraction = prospect.get("extraction") if isinstance(prospect.get("extraction"), dict) else {}
        ok, why = passes_active_buyer_gate(
            page_text,
            url=landing,
            action_date=str(prospect.get("action_date") or extraction.get("action_date") or ""),
            action_date_raw=str(prospect.get("action_date_raw") or extraction.get("action_date_raw") or ""),
            is_past_or_closed=bool(prospect.get("is_past_or_closed")),
            has_active_procurement=prospect.get("has_active_procurement"),
            buyer_signal_type=str(prospect.get("buyer_signal_type") or ""),
        )
        if not ok:
            return False, why

    return True, ""
