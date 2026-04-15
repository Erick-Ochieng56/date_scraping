from __future__ import annotations

import logging
from datetime import date
from urllib.parse import urlparse

from crawler.models import CrawlRun, DiscoveredDomain, EventProspect
from crawler.services.event_analyzer import analyze_event_page
from crawler.utils import normalize_url

logger = logging.getLogger(__name__)


def _resolve_owner_id(crawl_run: CrawlRun, discovered_domain: DiscoveredDomain) -> int | None:
    if crawl_run.owner_id:
        return int(crawl_run.owner_id)
    if discovered_domain.owner_id:
        return int(discovered_domain.owner_id)
    return None


def _event_url_is_specific(event_url: str) -> bool:
    """True when ``event_url`` points at a path, query, or fragment beyond the site root."""
    u = normalize_url((event_url or "").strip())
    if not u or not u.lower().startswith(("http://", "https://")):
        return False
    p = urlparse(u)
    path = (p.path or "").strip("/")
    if path:
        return True
    return bool((p.query or "").strip())


def process_event_domain(
    crawl_run: CrawlRun,
    discovered_domain: DiscoveredDomain,
    page_url_text_pairs: list[tuple[str, str]],
) -> int:
    """
    Analyze a domain for events and create EventProspect records.
    Returns count of newly created rows.
    """
    owner_id = _resolve_owner_id(crawl_run, discovered_domain)
    if not owner_id:
        logger.debug(
            "Skipping event prospects for domain=%s (no owner on run/domain)",
            discovered_domain.domain,
        )
        return 0

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        owner = User.objects.get(pk=owner_id)
    except User.DoesNotExist:
        return 0

    analysis = analyze_event_page(discovered_domain.domain, page_url_text_pairs)

    if not analysis.get("is_event_site"):
        return 0

    events_created = 0

    for event_data in analysis.get("events", []):
        raw_score = int(event_data.get("translation_need_score", 0))
        event_url = (event_data.get("event_url") or "").strip()
        if not _event_url_is_specific(event_url):
            raw_score = max(0, raw_score - 30)

        if raw_score < 40:
            continue

        event_date = None
        raw_date = event_data.get("event_date", "")
        if raw_date:
            try:
                event_date = date.fromisoformat(raw_date)
                if event_date < date.today():
                    continue
            except ValueError:
                pass

        event_name = event_data.get("event_name", "Unknown Event") or "Unknown Event"
        organizer_domain = discovered_domain.domain

        _obj, created = EventProspect.objects.update_or_create(
            event_name=event_name,
            organizer_domain=organizer_domain,
            defaults={
                "owner": owner,
                "discovered_domain": discovered_domain,
                "event_type": event_data.get("event_type", "other"),
                "organizer_name": event_data.get("organizer_name", ""),
                "event_url": event_data.get("event_url", "") or "",
                "event_date": event_date,
                "event_date_raw": event_data.get("event_date_raw", ""),
                "event_location": event_data.get("event_location", ""),
                "is_virtual": bool(event_data.get("is_virtual", False)),
                "is_hybrid": bool(event_data.get("is_hybrid", False)),
                "languages_involved": event_data.get("languages_involved", []),
                "countries_involved": event_data.get("countries_involved", []),
                "expected_attendee_count": event_data.get(
                    "expected_attendee_count", ""
                ),
                "translation_services_needed": event_data.get(
                    "translation_services_needed", []
                ),
                "translation_need_score": raw_score,
                "urgency_score": int(event_data.get("urgency_score", 0)),
                "contact_email": event_data.get("contact_email", ""),
                "contact_name": event_data.get("contact_name", ""),
                "contact_phone": event_data.get("contact_phone", ""),
            },
        )
        if created:
            events_created += 1

    return events_created
