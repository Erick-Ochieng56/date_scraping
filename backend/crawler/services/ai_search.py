from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from django.conf import settings
from google.genai import types

from crawler.services.gemini_client import generate_text

logger = logging.getLogger(__name__)

# Phrases that indicate the buyer needs LSP-style services (not generic event buzz).
_INTENT_MARKERS = (
    "interpretation",
    "translator",
    "translation",
    "localization",
    "localisation",
    "tender",
    "rfp",
    "procurement",
    "simultaneous",
    "conference equipment",
    "interpretation booth",
    "sign language",
    "rapporteur",
    "multilingual",
    "accessibility",
    "ungm",
    "world bank tender",
    "equipment hire",
    "pa system",
    "reliefweb",
)

_LSP_SERVICE_CONTEXT = """
Our company is a Language Service Provider (LSP) selling to BUYERS (not to other LSPs).
Core services to match prospects against:
- Translation and localization
- Conference interpretation (simultaneous, consecutive, equipment)
- Sign language interpreting
- Rapporteuring
- Copy-editing and publishing
- Conference equipment and PA systems

Prospects are organizations that likely need to BUY these services (events, NGOs, law,
health, government, multinationals, associations, conference organizers posting tenders).
"""


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s[: s.rfind("```")].strip()
    return s


def _query_has_buyer_intent(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in _INTENT_MARKERS)


def _is_broad_event_only_seed(seed: str) -> bool:
    """Topics like 'International Conference 2026' lack buyer/service signals."""
    s = (seed or "").strip().lower()
    if len(s) < 8:
        return True
    if re.search(r"\b20[2-3][0-9]\b", s) and "conference" in s and not _query_has_buyer_intent(s):
        return True
    if "international conference" in s and not _query_has_buyer_intent(s):
        return True
    return False


def _normalize_query_items(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        raw = [raw] if raw else []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = (item.get("query") or "").strip()
        if not q:
            continue
        out.append(
            {
                "query": q,
                "intent": (item.get("intent") or "").strip() or "Generated search angle",
                "expected_prospect_type": (item.get("expected_prospect_type") or "unknown").strip(),
            }
        )
    return out


def _dedupe_queries(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        k = it["query"].lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _boost_queries_for_lsp(
    seed_topic: str,
    industry: str,
    region: str,
    parsed: list[dict],
    count: int,
) -> list[dict]:
    """
    Broad event-style seeds produce SERPs with directories and news, not buyer intent.
    Inject high-intent procurement / multilingual-event queries and ensure buyer signals.
    """
    seed = (seed_topic or "").strip()
    geo = (region or "").strip() or "Kenya Uganda Tanzania Rwanda East Africa"
    ind = (industry or "").strip()
    ind_bit = f"{ind} " if ind else ""

    inject: list[dict] = []
    if _is_broad_event_only_seed(seed):
        inject.extend(
            [
                {
                    "query": f'{geo} {seed} simultaneous interpretation tender RFP',
                    "intent": "Buyers posting interpretation or AV procurement for events",
                    "expected_prospect_type": "event_organizer_or_government",
                },
                {
                    "query": f"{geo} multilingual conference accessibility sign language interpreter booking",
                    "intent": "Events explicitly needing accessibility / SLI",
                    "expected_prospect_type": "association_or_corporate_events",
                },
                {
                    "query": f"{ind_bit}UNGM OR reliefweb interpretation translation services tender",
                    "intent": "High-intent NGO / multilateral procurement language needs",
                    "expected_prospect_type": "ngo_or_donor_funded",
                },
            ]
        )

    templates = [
        {
            "query": f"{geo} conference interpretation equipment hire simultaneous booths",
            "intent": "Organizations renting interpretation infrastructure (strong LSP signal)",
            "expected_prospect_type": "event_organizer",
        },
        {
            "query": f"{geo} legal firm cross-border litigation translation sworn translator NOT agency",
            "intent": "Law practices with document translation demand",
            "expected_prospect_type": "law_firm",
        },
        {
            "query": f"{geo} hospital patient information multilingual translation policy",
            "intent": "Healthcare providers with multilingual comms obligations",
            "expected_prospect_type": "hospital",
        },
    ]

    merged = _dedupe_queries(inject + _normalize_query_items(parsed))

    for t in templates:
        if len(merged) >= count:
            break
        merged.append(t)
    merged = _dedupe_queries(merged)

    # Drop or rewrite queries that still lack any buyer-intent token (except first fallback).
    refined: list[dict] = []
    for it in merged:
        if _query_has_buyer_intent(it["query"]) or _query_has_buyer_intent(seed):
            refined.append(it)
        else:
            refined.append(
                {
                    **it,
                    "query": f"{it['query']} translation OR interpretation procurement",
                    "intent": it.get("intent", "") + " (buyer-intent suffix)",
                }
            )
        if len(refined) >= count:
            break

    if not refined and seed:
        refined = [
            {
                "query": f"{geo} {seed} interpretation OR translation tender",
                "intent": "fallback buyer-intent query",
                "expected_prospect_type": "unknown",
            }
        ]

    return refined[:count]


def generate_search_queries(
    seed_topic: str,
    industry: str = "",
    region: str = "",
    count: int = 10,
) -> list[dict]:
    model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")
    industry_line = f"Industry / sector focus: {industry}" if industry else ""
    region_line = (
        f"Geographic focus (anchor searches here; default East Africa if blank): {region}"
        if region
        else "Geographic focus: prefer Kenya, Uganda, Tanzania, Rwanda, Ethiopia, "
        "South Sudan, DRC — anchor every query with at least one regional token "
        "unless the seed is already global procurement (UNGM, World Bank)."
    )

    prompt = f"""
{_LSP_SERVICE_CONTEXT}

You generate Google search QUERY STRINGS for lead discovery.

Seed topic or event phrase from the user: "{seed_topic}"
{industry_line}
{region_line}

Generate {count} DISTINCT queries. Each query must help find BUYERS of language services,
not directories of translation companies and not generic event calendars with no
procurement angle.

Critical rules:
- NEVER output queries that only mention a year + "conference" / "summit" without also
  mentioning interpretation, translation, tender, RFP, procurement, multilingual,
  accessibility, equipment hire, rapporteur, or similar BUYER signals.
- Prefer angles: tenders/RFPs, UNGM/NGO procurement, hiring "freelance interpreter",
  "simultaneous interpretation required", annual reports in multiple languages,
  cross-border litigation, patient information multilingual, conference AV + interpretation.
- EXCLUDE queries optimized to find translation agencies (e.g. "top translation companies").
- Mix organization types: conference organizers, INGOs, ministries, hospitals, law firms,
  universities, associations, ecommerce regional HQs.

Return ONLY valid JSON array:
[
    {{
        "query": "exact string for Google",
        "intent": "why a real buyer might appear in results",
        "expected_prospect_type": "short label e.g. event_organizer, ngo, ministry"
    }}
]
"""

    try:
        raw_text = generate_text(model=model_name, prompt=prompt)
    except Exception as e:
        logger.warning("generate_search_queries failed: %s", e)
        raw_text = ""
    raw = _strip_code_fence(raw_text)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = []

    boosted = _boost_queries_for_lsp(seed_topic, industry, region, data, count)
    if not boosted:
        boosted = [
            {
                "query": (seed_topic or "translation services tender").strip(),
                "intent": "fallback",
                "expected_prospect_type": "unknown",
            }
        ]
    return boosted


def grounded_prospect_search(
    topic: str,
    region: str = "",
    max_results: int = 20,
) -> list[dict]:
    """
    Gemini with Google Search grounding via ``google-genai`` (``GoogleSearch`` tool).
    Falls back to empty list on failure (caller may use query-based discovery instead).
    """
    if not (getattr(settings, "GEMINI_API_KEY", None) or "").strip():
        return []

    region_line = f"Geographic focus: {region}" if region else (
        "Geographic focus: prioritize Kenya and East Africa; include pan-African "
        "and multilateral institutions when relevant."
    )
    prompt = f"""
{_LSP_SERVICE_CONTEXT}

Use web search to identify up to {max_results} REAL organizations (with real domains)
that are likely BUYERS of translation, localization, conference interpretation,
sign language interpreting, rapporteuring, copy-editing/publishing, or conference
equipment — not language agencies.

Topic / hook from the user: "{topic}"
{region_line}

Prefer:
- Conference organizers or venues publishing RFPs for interpretation or AV
- NGOs and multilaterals with multilingual programmes or tender pages
- Law firms, hospitals, government sites with cross-language needs

For each prospect return:
- domain (root host only, e.g. example.com)
- source_url (REQUIRED when your evidence comes from a specific page: full https URL of
  that page — tender detail, /events/…, conference listing, etc. Use the canonical
  page URL, not the site homepage, whenever the signal is on a deeper URL.)
- org_name
- org_type (short label)
- why_needs_translation (one sentence; mention the specific service signal you saw)
- international_signals (short strings or empty list)
- contact_email (if found, else "")

EXCLUDE translation agencies, LSPs, freelance marketplaces for linguists only.

Return ONLY a JSON array of objects.
"""

    grounded_model_name = getattr(
        settings, "GEMINI_GROUNDED_MODEL", "gemini-2.5-flash"
    )
    tools = [types.Tool(google_search=types.GoogleSearch())]

    try:
        raw_text = generate_text(
            model=grounded_model_name,
            prompt=prompt,
            tools=tools,
        )
        raw = _strip_code_fence(raw_text)
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("grounded_prospect_search failed: %s", e)
        return []


def validate_domain_exists(domain: str, *, timeout: float = 12.0) -> bool:
    """HTTP reachability check. Use a shorter timeout when validating many hosts in one job."""
    domain = domain.strip().lower().removeprefix("www.")
    if not domain:
        return False
    try:
        r = httpx.get(f"https://{domain}", timeout=timeout, follow_redirects=True)
        return r.status_code < 500
    except Exception:
        return False


def validate_landing_url(url: str, *, timeout: float = 12.0) -> bool:
    """HTTP reachability for a full URL (e.g. Serper landing page or grounded ``source_url``)."""
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return False
    try:
        r = httpx.get(u, timeout=timeout, follow_redirects=True)
        return r.status_code < 500
    except Exception:
        return False
