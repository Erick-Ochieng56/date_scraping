"""
Active-buyer and forward-timeline checks for AI search qualification.

Distinguishes organizations actively procuring language services from institutional
homepages, careers pages, and past events. Official procurement portals are allowed
when they list verifiable, current language-service opportunities.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

from crawler.services.event_validation import parse_event_date
from crawler.services.geo_filter import domain_has_ea_tld

_ACTIVE_PROCUREMENT_PHRASES = (
    "request for proposal",
    "request for proposals",
    "request for quotation",
    "invitation to tender",
    "invitation to bid",
    "call for proposals",
    "call for tenders",
    "expression of interest",
    "procurement notice",
    "tender notice",
    "bid opening",
    "submission deadline",
    "closing date",
    "deadline for submission",
    "bids due",
    "submit proposals by",
    "provision of translation",
    "provision of interpretation",
    "translation services required",
    "interpretation services required",
    "simultaneous interpretation for",
    "conference interpretation for",
    " hire interpreter",
    " hiring interpreter",
    "interpreter needed",
    "translators required",
    "interpretation booth",
)

_LANGUAGE_OPPORTUNITY_TERMS = (
    "interpret",
    "translat",
    "language service",
    "simultaneous",
    "multilingual",
    "locali",
    "sign language",
    "rapporteur",
)

_OPEN_OR_FUTURE_PHRASES = (
    "upcoming",
    "register now",
    "registration open",
    "will be held",
    "takes place on",
    "save the date",
    "open for applications",
    "currently accepting",
    "now accepting",
    "applications open",
    "open tender",
    "current opportunit",
    "active tender",
    "open procurement",
)

_CAREERS_HUB_MARKERS = (
    "/careers",
    "/work-with-us",
    "/work-field",
    "/vacancies",
    "/jobs/in-",
    "/child-protection-vacancies",
)

_PROCUREMENT_PORTAL_PATH_MARKERS = (
    "/procurement",
    "/tenders",
    "/tender/",
    "/procurement-notices",
    "/procurement-opportunities",
    "/invitation-to-tender",
    "/invitations-to-tender",
    "/bid-opportunities",
    "/business-opportunities",
)

# Third-party scrapers/republishers — not official buyer procurement portals.
_TENDER_AGGREGATOR_DOMAIN_FRAGMENTS = (
    "kenyatenders.com",
    "tenderimpulse.com",
    "tendersinfo.com",
    "tenderskenya.co.ke",
    "developmentaid.org",
    "globaltenders.com",
    "tendersontime.com",
)

# Document mirrors and republished files — not live portal pages.
_PROCUREMENT_HOST_BLOCK_FRAGMENTS = (
    "documents1.worldbank.org",
    "documents.worldbank.org",
)

# Recognised multilateral procurement portals (main site, not document CDN).
_VERIFIED_MULTILATERAL_PORTAL_HOSTS = (
    "worldbank.org",
    "ungm.org",
    "unido.org",
    "procurement-notices.undp.org",
)

_OFFICIAL_PORTAL_TLD_MARKERS = (
    ".go.ke",
    ".go.ug",
    ".go.tz",
    ".gov",
    ".gob.",
    ".gouv.",
)

_STALE_URL_YEAR = re.compile(r"/(?:19|20)\d{2}(?:[/_-]|$)")

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
    "closed tender",
    "tender closed",
    "award notice",
    "contract awarded",
)

_DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+20\d{2})\b",
    re.IGNORECASE,
)

_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

# Truncate page text before sidebars/footers that pollute year checks (e.g. 2026 news widgets).
_FOOTER_MARKERS = (
    "contact us",
    "read more about",
    "#### news",
    "\nnews\n",
    "#### faq",
    "case tracker",
    "volunteer",
    "go to campaign",
)

_DEADLINE_CONTEXT_PHRASES = (
    "deadline",
    "closing date",
    "submit by",
    "submission deadline",
    "should reach",
    "must reach",
    "reach ",
    " by ",
    "due date",
    "no later than",
    "before ",
    "closes on",
)


def _host_from(domain: str = "", url: str = "") -> str:
    host = urlparse((domain or url or "").strip()).netloc.lower().removeprefix("www.")
    if not host and domain and "." in domain and "://" not in domain:
        host = domain.lower().removeprefix("www.")
    return host


def _looks_like_past_event_text(event_date_raw: str = "", extra_text: str = "") -> bool:
    combined = f"{event_date_raw} {extra_text}".lower()
    if any(p in combined for p in _PAST_EVENT_PHRASES):
        return True
    years = _year_tokens_in_text(combined)
    if years and max(years) < date.today().year:
        return True
    return False


def _year_tokens_in_text(text: str) -> list[int]:
    return [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")]


def crawler_require_active_buyer() -> bool:
    from django.conf import settings

    if hasattr(settings, "CRAWLER_REQUIRE_ACTIVE_BUYER"):
        return bool(settings.CRAWLER_REQUIRE_ACTIVE_BUYER)
    return bool(getattr(settings, "AI_SEARCH_REQUIRE_ACTIVE_BUYER", True))


def is_buyer_procurement_context(text: str) -> bool:
    """True when page text looks like a buyer posting or procuring language services."""
    low = f" {(text or '').lower()} "
    if any(p in low for p in _ACTIVE_PROCUREMENT_PHRASES):
        return True
    if re.search(r"\b(rfp|rfq|rfi)\b", low):
        return True
    if " tender " in low and any(w in low for w in ("closing", "deadline", "submit", "procurement")):
        return True
    return False


def _mentions_language_opportunity(text: str) -> bool:
    low = (text or "").lower()
    return any(term in low for term in _LANGUAGE_OPPORTUNITY_TERMS)


def is_procurement_portal_listing_url(url: str) -> bool:
    """
    True for procurement portal index/listing pages — not individual tender notice URLs.
    """
    path = urlparse((url or "").strip()).path.lower().rstrip("/") or "/"
    if path in ("/", ""):
        return False

    if "/tenders/" in path:
        return False
    if re.search(r"/procurement-notices/[^/]+", path):
        return False
    if re.search(r"/procurement/[^/]+", path) and not path.endswith("/procurement"):
        return False

    listing_endings = (
        "/procurement-notices",
        "/procurement-opportunities",
        "/projects-operations/procurement",
        "/business-opportunities",
        "/bid-opportunities",
        "/invitations-to-tender",
        "/invitation-to-tender",
        "/procurement",
        "/procurements",
        "/tender",
        "/tenders",
    )
    if path in listing_endings or any(path.endswith(e) for e in listing_endings):
        return True
    return any(e in path for e in ("/procurement-notices", "/procurement-opportunities"))


def is_procurement_portal_url(url: str) -> bool:
    """Alias: listing-style procurement portal (not a single tender page)."""
    return is_procurement_portal_listing_url(url)


def is_third_party_tender_aggregator(domain: str = "", url: str = "") -> bool:
    host = _host_from(domain, url)
    return any(frag in host for frag in _TENDER_AGGREGATOR_DOMAIN_FRAGMENTS)


def is_verifiable_procurement_portal(
    domain: str = "",
    *,
    url: str = "",
    page_text: str = "",
) -> tuple[bool, str]:
    """
    True for official buyer-hosted procurement portals — not third-party aggregators
    or document mirrors.
    """
    host = _host_from(domain, url)
    if not host:
        return False, "Could not determine portal host."

    if is_third_party_tender_aggregator(host):
        return False, "Third-party tender aggregator — not an official buyer portal."

    for frag in _PROCUREMENT_HOST_BLOCK_FRAGMENTS:
        if frag in host:
            return False, f"Document mirror host is not a live procurement portal: {frag}"

    if not is_procurement_portal_listing_url(url) and urlparse((url or "").strip()).path.rstrip("/") in ("", "/"):
        return False, "Org homepage is not a procurement portal."

    if any(host == h or host.endswith("." + h) for h in _VERIFIED_MULTILATERAL_PORTAL_HOSTS):
        low = (page_text or "").lower()[:8000]
        if is_buyer_procurement_context(low) or any(
            p in low for p in ("procurement", "tender", "current opportunit", "open tender")
        ):
            return True, ""
        return False, "Multilateral host without procurement portal content."

    if domain_has_ea_tld(host) or any(m in host for m in _OFFICIAL_PORTAL_TLD_MARKERS):
        return True, ""

    if host.endswith(".org") or host.endswith(".or.ke") or host.endswith(".ac.ke"):
        low = (page_text or "").lower()[:6000]
        if is_procurement_portal_url(url) and (
            is_buyer_procurement_context(low)
            or "procurement" in low
            or "tender" in low
        ):
            return True, ""

    return False, "Not a verifiable official procurement portal."


def _chunk_dates(chunk: str, *, today: date) -> list[date]:
    found: list[date] = []
    for iso in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", chunk):
        parsed = parse_event_date(iso)
        if parsed:
            found.append(parsed)
    for match in _DATE_TEXT_RE.finditer(chunk):
        parsed = parse_event_date(match.group(1))
        if parsed:
            found.append(parsed)
    for year in _year_tokens_in_text(chunk):
        if year >= today.year:
            found.append(date(year, 12, 31))
    return found


def _portal_opportunity_chunks(text: str) -> list[str]:
    """Build candidate blocks from portal listings (title + deadline may be on adjacent lines)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    candidates: list[str] = []
    for i, line in enumerate(lines):
        candidates.append(line)
        if i + 1 < len(lines):
            candidates.append(f"{line} {lines[i + 1]}")
    if len(candidates) <= 1:
        return [text]
    return candidates


def _chunk_is_current_opportunity(chunk: str, *, today: date) -> bool:
    dates = _chunk_dates(chunk, today=today)
    if any(d >= today for d in dates):
        return True
    years = _year_tokens_in_text(chunk)
    if years and max(years) >= today.year and (
        is_buyer_procurement_context(chunk) or _mentions_language_opportunity(chunk)
    ):
        return True

    chunk_low = chunk.lower()
    if any(p in chunk_low for p in ("closed", "awarded", "was held", "archive")):
        return False
    if _looks_like_past_event_text(extra_text=chunk):
        return False
    if any(p in chunk_low for p in _OPEN_OR_FUTURE_PHRASES):
        if not years or any(y >= today.year for y in years):
            return True
    return False


def portal_has_current_language_opportunity(
    page_text: str,
    *,
    today: date | None = None,
) -> tuple[bool, str]:
    """
    On a procurement portal listing, require at least one current (not past)
    opportunity related to language services.
    """
    today = today or date.today()
    text = (page_text or "").strip()
    if len(text) < 80:
        return False, "Procurement portal page has insufficient text."

    if not is_buyer_procurement_context(text) and not _mentions_language_opportunity(text):
        return False, "Procurement portal has no tender or language-service notices."

    chunks = _portal_opportunity_chunks(text)
    current_language: list[str] = []
    past_language: list[str] = []

    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 40:
            continue
        if not _mentions_language_opportunity(chunk):
            continue
        if not (
            is_buyer_procurement_context(chunk)
            or "tender" in chunk.lower()
            or "rfp" in chunk.lower()
            or "procurement" in chunk.lower()
        ):
            continue
        if _chunk_is_current_opportunity(chunk, today=today):
            current_language.append(chunk)
        else:
            past_language.append(chunk)

    if current_language:
        return True, ""

    if past_language:
        return False, "Procurement portal lists only past language-service tenders or events."

    if _chunk_is_current_opportunity(text, today=today) and _mentions_language_opportunity(text):
        if is_buyer_procurement_context(text):
            return True, ""

    return False, "No current language-service opportunity on this procurement portal."


def best_portal_opportunity_snippet(page_text: str, *, today: date | None = None) -> str:
    """Return the best current language-opportunity snippet from a portal page."""
    today = today or date.today()
    for chunk in _portal_opportunity_chunks(page_text or ""):
        chunk = chunk.strip()
        if len(chunk) < 40:
            continue
        if _mentions_language_opportunity(chunk) and _chunk_is_current_opportunity(chunk, today=today):
            if is_buyer_procurement_context(chunk) or "tender" in chunk.lower() or "rfp" in chunk.lower():
                return chunk[:500]
    return ""


def _homepage_shows_lsp_relevance(page_text: str) -> bool:
    """
    True when a homepage's own content plausibly indicates translation/
    interpretation/localization need — a detected service or org-type signal,
    or an international/multilingual indicator — rather than being generic.
    """
    from crawler.analyzer import build_international_signals, detect_org_types, detect_services

    text = (page_text or "").strip()
    if not text:
        return False
    if detect_services(text) or detect_org_types(text) or build_international_signals(text):
        return True
    return _mentions_language_opportunity(text)


def is_org_homepage_or_careers_hub(url: str, page_text: str = "") -> bool:
    """Reject org front doors and careers sections (not procurement portals)."""
    path = urlparse((url or "").strip()).path.lower().rstrip("/") or "/"
    if path in ("/", ""):
        # A homepage is a "generic hub" (reject) only when its own content shows
        # no LSP-relevant signal at all. Previously ANY root URL was rejected
        # unconditionally regardless of content — but a normal search for
        # "NGO language services Africa" or "international conference" mostly
        # returns organization homepages, so this discarded most organic,
        # on-target hits before scoring ever ran (DISCOVERY_QUALITY_ANALYSIS.md F1).
        return not _homepage_shows_lsp_relevance(page_text)
    if is_procurement_portal_url(url):
        return False
    for marker in _CAREERS_HUB_MARKERS:
        m = marker.rstrip("/")
        if path == m or path.endswith(m) or marker in path:
            if is_buyer_procurement_context(page_text) and _mentions_language_opportunity(page_text):
                return False
            return True
    return False


def is_generic_hub_page(url: str, page_text: str = "", *, domain: str = "") -> bool:
    """
    True when the URL should be dropped as a non-actionable hub page.
    Official procurement portals with current opportunities return False.
    """
    if is_procurement_portal_url(url):
        verifiable, _ = is_verifiable_procurement_portal(domain, url=url, page_text=page_text)
        if not verifiable:
            return True
        current, _ = portal_has_current_language_opportunity(page_text)
        return not current
    return is_org_homepage_or_careers_hub(url, page_text)


def preflight_candidate_page(
    url: str,
    page_text: str,
    *,
    domain: str = "",
) -> tuple[bool, str]:
    """Early gate before Gemini. False = drop with reason."""
    if url_looks_stale(url):
        return False, "URL points to archived document from a past year."

    host = _host_from(domain, url)

    if is_procurement_portal_url(url):
        verifiable, reason = is_verifiable_procurement_portal(host, url=url, page_text=page_text)
        if not verifiable:
            return False, reason
        current, reason = portal_has_current_language_opportunity(page_text)
        if not current:
            return False, reason
        return True, ""

    if is_org_homepage_or_careers_hub(url, page_text):
        return False, "Generic org or careers page — no specific opportunity."

    return True, ""


def has_active_buyer_signal(page_text: str, *, url: str = "", domain: str = "") -> tuple[bool, str]:
    ok, reason = preflight_candidate_page(url, page_text, domain=domain)
    if not ok:
        return False, reason
    if not is_buyer_procurement_context(page_text):
        return False, "No active tender, RFP, event procurement, or interpreter hiring on page."
    # is_buyer_procurement_context only detects generic tender/RFP/grant phrasing
    # ("request for proposals", "closing date", etc.) — it has no idea what the
    # tender is FOR. Without this check, any active procurement notice passed
    # regardless of subject (e.g. a hospital-equipment grant page), even though it
    # has nothing to do with translation/interpretation/language services.
    if not _mentions_language_opportunity(page_text):
        return False, (
            "Active tender/RFP/procurement found, but it is not about translation, "
            "interpretation, or language services."
        )
    return True, ""


def _years_embedded_in_url(url: str) -> list[int]:
    """Find 4-digit years anywhere in a URL (path, slug, query) — catches ...42014, /2014/, etc."""
    return [int(y) for y in re.findall(r"(?:19|20)\d{2}", (url or "").lower())]


def _normalize_date_phrase(raw: str) -> str:
    return re.sub(r"(\d{1,2})(?:st|nd|rd|th)", r"\1", (raw or "").strip(), flags=re.IGNORECASE)


def _primary_opportunity_text(text: str, *, max_chars: int = 6000) -> str:
    """Main article body only — exclude sidebars/news blocks that add unrelated future years."""
    body = (text or "").strip()
    if not body:
        return ""
    low = body.lower()
    cut = len(body)
    for marker in _FOOTER_MARKERS:
        idx = low.find(marker)
        if idx > 400:
            cut = min(cut, idx)
    return body[: min(cut, max_chars)]


def _parse_dates_in_chunk(chunk: str) -> list[date]:
    found: list[date] = []
    for iso in _ISO_DATE_RE.findall(chunk):
        parsed = parse_event_date(iso)
        if parsed:
            found.append(parsed)
    for match in _DATE_TEXT_RE.finditer(chunk):
        parsed = parse_event_date(_normalize_date_phrase(match.group(1)))
        if parsed:
            found.append(parsed)
    for match in re.finditer(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s*,?\s*(20\d{2})\b",
        chunk,
        re.IGNORECASE,
    ):
        parsed = parse_event_date(f"{match.group(1)} {match.group(2)} {match.group(3)}")
        if parsed:
            found.append(parsed)
    return found


def _procurement_deadline_dates(text: str) -> list[date]:
    """Dates appearing near submission/closing language in the primary opportunity section."""
    primary = _primary_opportunity_text(text)
    dates: list[date] = []
    for chunk in re.split(r"[\n\r]+|(?<=\.)\s+", primary):
        chunk = chunk.strip()
        if len(chunk) < 12:
            continue
        cl = chunk.lower()
        if not any(p in cl for p in _DEADLINE_CONTEXT_PHRASES):
            if not any(p in cl for p in ("rfp", "tender", "expression of interest", "eoi")):
                continue
        dates.extend(_parse_dates_in_chunk(chunk))
    return dates


def _language_chunks_with_current_deadline(text: str, *, today: date) -> bool:
    """True when a language-service line item is tied to a current/future procurement date."""
    primary = _primary_opportunity_text(text)
    deadlines = _procurement_deadline_dates(text)
    has_future_deadline = any(d >= today for d in deadlines)
    has_past_only_deadline = bool(deadlines) and all(d < today for d in deadlines)

    if has_past_only_deadline:
        return False

    for chunk in _portal_opportunity_chunks(primary):
        if not _mentions_language_opportunity(chunk):
            continue
        if not (
            is_buyer_procurement_context(chunk)
            or "rfp" in chunk.lower()
            or "tender" in chunk.lower()
            or "eoi" in chunk.lower()
        ):
            continue
        if _chunk_is_current_opportunity(chunk, today=today):
            return True

    if has_future_deadline and _mentions_language_opportunity(primary):
        return True
    return False


def url_looks_stale(url: str, *, today: date | None = None) -> bool:
    """Reject URLs anchored to old years in path, slug, or reference codes (e.g. ...42014, /2014/)."""
    today = today or date.today()
    u = (url or "").lower()
    embedded = _years_embedded_in_url(u)
    if embedded and max(embedded) < today.year - 1:
        return True
    for match in _STALE_URL_YEAR.finditer(u):
        year = int(match.group(0).strip("/_-")[:4])
        if year < today.year - 1:
            return True
    return False


def check_forward_timeline(
    page_text: str,
    *,
    action_date: str = "",
    action_date_raw: str = "",
    is_past_or_closed: bool = False,
    url: str = "",
    today: date | None = None,
) -> tuple[bool, str]:
    """
    Require current or future opportunity — reject past events and stale pages.
    """
    today = today or date.today()
    text = (page_text or "").strip()

    if is_past_or_closed:
        return False, "Opportunity is past or closed."

    if url and is_procurement_portal_url(url):
        host = _host_from(url=url)
        verifiable, reason = is_verifiable_procurement_portal(host, url=url, page_text=text)
        if not verifiable:
            return False, reason
        return portal_has_current_language_opportunity(text, today=today)

    if url and url_looks_stale(url, today=today):
        return False, "URL points to archived document from a past year."

    primary = _primary_opportunity_text(text)

    deadlines = _procurement_deadline_dates(text)
    if deadlines:
        if all(d < today for d in deadlines):
            past = min(deadlines).isoformat()
            return False, f"Procurement deadline {past} is in the past."

    url_years = _years_embedded_in_url(url or "")
    if url_years and max(url_years) < today.year and not any(d >= today for d in deadlines):
        return False, "URL references a past procurement year with no current deadline."

    for raw in (action_date, action_date_raw):
        parsed = parse_event_date(raw)
        if parsed and parsed < today:
            return False, f"Opportunity date {parsed.isoformat()} is in the past."

    if _looks_like_past_event_text(action_date_raw, extra_text=primary):
        if not any(p in primary.lower() for p in _OPEN_OR_FUTURE_PHRASES):
            future_year_mentioned = any(y >= today.year for y in _year_tokens_in_text(primary))
            if not future_year_mentioned:
                return False, "Page describes a past or archived event."

    years = _year_tokens_in_text(primary)
    if years:
        has_future = any(y >= today.year for y in years)
        has_past_only = all(y < today.year for y in years)
        if has_past_only and not any(p in primary.lower() for p in _OPEN_OR_FUTURE_PHRASES):
            if not any(d >= today for d in deadlines):
                return False, "Page only references past years with no current opportunity."

        if not has_future and max(years) < today.year:
            if not is_buyer_procurement_context(primary) and not any(d >= today for d in deadlines):
                return False, "Content appears historical with no forward-looking date."

    if is_buyer_procurement_context(primary) and _mentions_language_opportunity(primary):
        if deadlines and all(d < today for d in deadlines):
            return False, "Language-service procurement deadline is in the past."
        if not deadlines and url_years and max(url_years) < today.year:
            return False, "Language-service opportunity is from a past year."

    return True, ""


def passes_active_buyer_gate(
    page_text: str,
    *,
    url: str = "",
    domain: str = "",
    action_date: str = "",
    action_date_raw: str = "",
    is_past_or_closed: bool = False,
    has_active_procurement: bool | None = None,
    buyer_signal_type: str = "",
    today: date | None = None,
) -> tuple[bool, str]:
    """Combined active-buyer + forward-timeline gate for AI search."""
    ok, reason = check_forward_timeline(
        page_text,
        action_date=action_date,
        action_date_raw=action_date_raw,
        is_past_or_closed=is_past_or_closed,
        url=url,
        today=today,
    )
    if not ok:
        return False, reason

    # has_active_procurement is an upstream (often Gemini-extracted) flag meaning
    # "this page shows an open tender/RFP/hiring notice right now" — it says nothing
    # about the SUBJECT of that opportunity. Trusting it alone let procurement pages
    # for unrelated goods (e.g. a hospital-equipment grant) pass as language-service
    # leads; _mentions_language_opportunity is the missing subject-matter check.
    if has_active_procurement is True and _mentions_language_opportunity(page_text):
        return True, ""

    primary = _primary_opportunity_text(page_text)
    if _mentions_language_opportunity(primary) and is_buyer_procurement_context(primary):
        today = today or date.today()
        if not _language_chunks_with_current_deadline(page_text, today=today):
            return False, (
                "Language-service opportunity is outdated (past deadline or past reference year)."
            )

    if is_procurement_portal_url(url):
        host = _host_from(domain, url)
        verifiable, reason = is_verifiable_procurement_portal(host, url=url, page_text=page_text)
        if not verifiable:
            return False, reason
        return portal_has_current_language_opportunity(page_text, today=today or date.today())

    signal = (buyer_signal_type or "").strip().lower()
    if signal in ("tender", "event", "hiring", "programme"):
        if (is_buyer_procurement_context(page_text) or signal == "hiring") and _mentions_language_opportunity(
            page_text
        ):
            return True, ""

    return has_active_buyer_signal(page_text, url=url, domain=domain)
