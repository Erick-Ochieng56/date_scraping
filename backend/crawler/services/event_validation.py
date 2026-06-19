from __future__ import annotations

import re
from datetime import date, datetime

from crawler.services.geo_filter import passes_geo_gate
from crawler.services.prospect_verify import looks_like_past_event_text

_MIN_SCORE_WITHOUT_DATE = 70
_MIN_SCORE_WITHOUT_SPECIFIC_URL = 60


def parse_event_date(raw: str) -> date | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:40], fmt).date()
        except ValueError:
            continue
    return None


def event_url_is_specific(event_url: str) -> bool:
    from urllib.parse import urlparse

    from crawler.utils import normalize_url

    u = normalize_url((event_url or "").strip())
    if not u or not u.lower().startswith(("http://", "https://")):
        return False
    p = urlparse(u)
    path = (p.path or "").strip("/")
    if path:
        return True
    return bool((p.query or "").strip())


def accept_event_candidate(event_data: dict, *, today: date | None = None) -> tuple[bool, str]:
    """
    Decide whether an extracted event should become an EventProspect.
    """
    today = today or date.today()
    raw_score = int(event_data.get("translation_need_score", 0) or 0)
    event_url = (event_data.get("event_url") or "").strip()
    event_date_raw = (event_data.get("event_date_raw") or "").strip()
    raw_date = (event_data.get("event_date") or "").strip()

    if not event_url_is_specific(event_url):
        raw_score = max(0, raw_score - 30)
        if raw_score < _MIN_SCORE_WITHOUT_SPECIFIC_URL:
            return False, "Event URL is not specific enough."

    event_date = parse_event_date(raw_date)
    if event_date and event_date < today:
        return False, "Event date is in the past."

    if looks_like_past_event_text(event_date_raw, extra_text=raw_date):
        return False, "Event text indicates a past or archived event."

    # Reject vague future claims without a parseable date unless score is high.
    if not event_date and not event_date_raw:
        if raw_score < _MIN_SCORE_WITHOUT_DATE:
            return False, "Missing event date for low-confidence event."

    if raw_score < 40:
        return False, "Translation need score below threshold."

    location_bits = [
        event_data.get("event_location", ""),
        " ".join(event_data.get("countries_involved") or []),
        event_data.get("event_name", ""),
        event_url,
        event_date_raw,
    ]
    geo_ok, geo_reason = passes_geo_gate(*[str(x) for x in location_bits if x], domain=event_url)
    if not geo_ok:
        return False, geo_reason

    return True, ""


def adjusted_event_score(event_data: dict) -> int:
    raw_score = int(event_data.get("translation_need_score", 0) or 0)
    event_url = (event_data.get("event_url") or "").strip()
    if not event_url_is_specific(event_url):
        raw_score = max(0, raw_score - 30)
    return raw_score
