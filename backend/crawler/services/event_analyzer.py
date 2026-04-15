from __future__ import annotations

import json
import logging
from datetime import date

from django.conf import settings

from crawler.services.gemini_client import generate_text

logger = logging.getLogger(__name__)


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s[: s.rfind("```")].strip()
    return s


def analyze_event_page(
    domain: str, page_url_text_pairs: list[tuple[str, str]]
) -> dict:
    today = date.today().isoformat()
    chunks: list[str] = []
    for url, text in page_url_text_pairs:
        u = (url or "").strip() or "(unknown URL — text only)"
        t = (text or "").strip()
        chunks.append(f"### Crawled page URL: {u}\n{t[:12_000]}")
    combined = "\n\n---PAGE BREAK---\n\n".join(chunks)[:30_000]
    model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")

    prompt = f"""
You are a lead qualification assistant for a Language Service Provider (LSP).
Today's date is {today}.

Analyze this website and extract ALL events that would likely need professional
translation, interpretation, or localization services.

Site / domain context: {domain}

Content is grouped by the real URL of each crawled page (see "### Crawled page URL:" headers).

Website content:
{combined}

For each event found, determine:
1. Does it involve multiple languages or countries?
2. Are there international speakers or attendees?
3. Would it need simultaneous interpretation, document translation, or subtitling?

CRITICAL — ``event_url``:
- Must be the full https URL of the page where THIS event is actually described
  (copy it exactly from one of the "### Crawled page URL:" lines when that page
  describes the event).
- Do NOT set ``event_url`` to the marketing homepage or bare domain root unless the
  homepage is literally the only page where that specific event appears AND you say so
  in ``event_date_raw`` reasoning.
- If the event is only mentioned generically across several pages, pick the most
  specific single URL (e.g. /events/conference-2026/, not /).

Scoring guide for translation_need_score (0-100):
- 90-100: Explicitly multilingual, international delegations, UN/AU style events
- 70-89: International attendees, multiple countries, no explicit language mention
- 50-69: Regional event with cross-border participation likely
- 30-49: Domestic but prestigious/large enough to attract foreigners
- 0-29: Purely local, single language

Urgency scoring (0-100):
- 100: Event in under 4 weeks
- 80: Event in 1-3 months
- 60: Event in 3-6 months
- 40: Event in 6-12 months
- 20: Event over 1 year away or date unknown

EXCLUDE: past events (before {today}), events run BY translation companies, webinars with no international component.

Return ONLY valid JSON:
{{
    "is_event_site": true/false,
    "events": [
        {{
            "event_name": "string",
            "event_type": "conference|summit|trade_show|workshop|diplomatic|legal|medical|ngo|government|other",
            "organizer_name": "string",
            "event_url": "full https URL from a Crawled page URL header, or empty if unknown",
            "event_date": "YYYY-MM-DD or empty string",
            "event_date_raw": "original date text from page",
            "event_location": "city, country",
            "is_virtual": false,
            "is_hybrid": false,
            "languages_involved": ["list of languages mentioned"],
            "countries_involved": ["list of countries mentioned"],
            "expected_attendee_count": "string e.g. 500+ or empty",
            "translation_services_needed": ["simultaneous interpretation|document translation|subtitling|sight translation|other"],
            "translation_need_score": 0,
            "urgency_score": 0,
            "contact_name": "string",
            "contact_email": "string",
            "contact_phone": "string"
        }}
    ]
}}
"""

    raw_text = generate_text(model=model_name, prompt=prompt)
    raw = _strip_code_fence(raw_text)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Event analyzer JSON parse failed for domain=%s", domain)
        return {"is_event_site": False, "events": []}
