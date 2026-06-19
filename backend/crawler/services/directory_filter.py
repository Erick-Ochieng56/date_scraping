from __future__ import annotations

from urllib.parse import urlparse

# Event calendars, marketplaces, and aggregators — not individual buyer orgs.
DIRECTORY_DOMAIN_FRAGMENTS = (
    "eventbrite.com",
    "10times.com",
    "cvent.com",
    "allevents.in",
    "meetup.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "wikipedia.org",
    "tripadvisor.com",
    "expedia.com",
    "booking.com",
    "internationalconferencealerts.com",
    "conferencealert.com",
    "waset.org",
    "allconferencealert.com",
    "tendersinfo.com",
    "tenderskenya.co.ke",
    "developmentaid.org",
    "researchgate.net",
    "instagram.com",
    "fliphtml5.com",
    "ncbi.nlm.nih.gov",
    "scholar.google.com",
    "arxiv.org",
    "kenyatenders.com",
    "tenderimpulse.com",
    "untalent.org",
    "unjobs.org",
    "documents1.worldbank.org",
    "dww.show",
    "afromedia.network",
)

_DIRECTORY_PATH_HINTS = (
    "/events/search",
    "/event-list",
    "/calendar",
    "/directory",
    "/listings",
    "/category/",
    "/work-with-us",
    "/careers",
    "/vacancies",
    "/jobs/in-",
)

_DIRECTORY_TEXT_HINTS = (
    "browse events",
    "events near you",
    "submit your event",
    "list your event",
    "thousands of events",
    "event directory",
    "find events",
)


def is_directory_or_aggregator(
    domain: str,
    *,
    url: str = "",
    page_text: str = "",
) -> tuple[bool, str]:
    from crawler.services.active_buyer import (
        is_procurement_portal_url,
        is_third_party_tender_aggregator,
        is_verifiable_procurement_portal,
    )

    host = urlparse((domain or "").strip()).netloc.lower().removeprefix("www.")
    if not host and "." in (domain or ""):
        host = (domain or "").lower().removeprefix("www.")

    if is_third_party_tender_aggregator(host):
        return True, f"Domain is a third-party tender aggregator: {host}"

    if is_procurement_portal_url(url):
        verifiable, _ = is_verifiable_procurement_portal(host, url=url, page_text=page_text)
        if verifiable:
            return False, ""

    for frag in DIRECTORY_DOMAIN_FRAGMENTS:
        if frag in host:
            return True, f"Domain is a known event directory/aggregator: {frag}"

    path = urlparse((url or "").strip()).path.lower()
    for hint in _DIRECTORY_PATH_HINTS:
        if hint in path:
            return True, f"URL looks like an event listing page ({hint})"

    low = (page_text or "").lower()[:6000]
    hits = [h for h in _DIRECTORY_TEXT_HINTS if h in low]
    if len(hits) >= 2:
        return True, f"Page reads like an event directory ({hits[0]})"

    return False, ""
