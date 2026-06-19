from __future__ import annotations

import re
from urllib.parse import urlparse

from django.conf import settings

# Canonical East Africa geography for strict filtering.
EAST_AFRICA_TERMS = (
    "east africa",
    "eac",
    "east african community",
    "kenya",
    "uganda",
    "tanzania",
    "rwanda",
    "burundi",
    "south sudan",
    "ethiopia",
    "eritrea",
    "nairobi",
    "mombasa",
    "kisumu",
    "kampala",
    "entebbe",
    "dar es salaam",
    "dodoma",
    "arusha",
    "kigali",
    "bujumbura",
    "juba",
    "addis ababa",
    "democratic republic of congo",
    "drc",
    "dr congo",
)

EAST_AFRICA_TLDS = (".ke", ".ug", ".tz", ".rw", ".bi", ".ss", ".et")

# Primary foreign locations — reject when present without an EA signal.
FOREIGN_PRIMARY_TERMS = (
    "united states",
    "u.s.a",
    " usa ",
    "united kingdom",
    " u.k.",
    " uk ",
    "germany",
    "france",
    "canada",
    "australia",
    "switzerland",
    "netherlands",
    "singapore",
    "china",
    "india",
    "dubai",
    "uae",
)

_MULTILATERAL_DOMAIN_FRAGMENTS = (
    "ungm.org",
    "worldbank.org",
    "usaid.gov",
    "reliefweb.int",
    "african-union.org",
    "au.int",
    "un.org",
)


def geo_mode() -> str:
    return (getattr(settings, "CRAWLER_GEO_MODE", "east_africa") or "east_africa").strip().lower()


def geo_strict_enabled() -> bool:
    return geo_mode() == "east_africa"


def default_region() -> str:
    return (
        getattr(
            settings,
            "CRAWLER_DEFAULT_REGION",
            "Kenya Uganda Tanzania Rwanda Burundi South Sudan Ethiopia East Africa EAC",
        )
        or "Kenya Uganda Tanzania Rwanda Burundi South Sudan Ethiopia East Africa EAC"
    ).strip()


def resolve_region(user_region: str = "") -> str:
    explicit = (user_region or "").strip()
    if explicit:
        return explicit
    if geo_strict_enabled():
        return default_region()
    return ""


def text_mentions_east_africa(text: str) -> bool:
    low = f" {(text or '').lower()} "
    return any(term in low for term in EAST_AFRICA_TERMS)


def domain_has_ea_tld(domain_or_url: str) -> bool:
    host = urlparse((domain_or_url or "").strip()).netloc.lower().removeprefix("www.")
    if not host and "." in (domain_or_url or ""):
        host = (domain_or_url or "").lower().removeprefix("www.")
    return any(host.endswith(tld) for tld in EAST_AFRICA_TLDS)


def is_multilateral_allowlist_domain(domain_or_url: str) -> bool:
    host = urlparse((domain_or_url or "").strip()).netloc.lower().removeprefix("www.")
    if not host:
        host = (domain_or_url or "").lower().removeprefix("www.")
    return any(frag in host for frag in _MULTILATERAL_DOMAIN_FRAGMENTS)


def text_mentions_foreign_primary(text: str) -> bool:
    low = f" {(text or '').lower()} "
    return any(term in low for term in FOREIGN_PRIMARY_TERMS)


def passes_geo_gate(*texts: str, domain: str = "") -> tuple[bool, str]:
    """
    When strict East Africa mode is on, require an EA geographic signal.
    """
    if not geo_strict_enabled():
        return True, ""

    combined = " ".join(t for t in texts if t).strip()
    dom = (domain or "").strip()

    if domain_has_ea_tld(dom):
        return True, ""

    if text_mentions_east_africa(combined):
        return True, ""

    if is_multilateral_allowlist_domain(dom):
        return False, "Multilateral source without East Africa location in page text."

    if text_mentions_foreign_primary(combined):
        return False, "Result appears to be outside East Africa."

    return False, "No East Africa geographic signal found."


def serper_geo_payload() -> dict[str, str]:
    """Serper location bias when strict geo mode is enabled."""
    if not geo_strict_enabled():
        return {}
    return {"gl": "ke", "location": "East Africa,Kenya"}


def ai_geo_rules_block(region: str) -> str:
    """Prompt fragment for Gemini search generation / grounding."""
    focus = region or default_region()
    if not geo_strict_enabled():
        if focus:
            return f"Geographic focus: {focus}"
        return (
            "Geographic focus: prioritize Kenya and East Africa; include pan-African "
            "and multilateral institutions when relevant."
        )

    return f"""Geographic focus (STRICT — East Africa only): {focus}
ONLY include organizations, events, and tenders with a clear location in East Africa
(Kenya, Uganda, Tanzania, Rwanda, Burundi, South Sudan, Ethiopia, Eritrea, DRC when
relevant to East Africa, and the East African Community).
EXCLUDE United States, UK, EU, Asia, Middle East, and other non-East-African results.
UN, AU, World Bank, UNGM, and ReliefWeb sources are allowed ONLY when the specific
tender or event location stated on the page is in East Africa."""


def ensure_query_has_geo(query: str, region: str) -> str:
    """Prepend regional tokens to discovery queries when missing in strict mode."""
    q = (query or "").strip()
    if not q or not geo_strict_enabled():
        return q
    if text_mentions_east_africa(q):
        return q
    geo = resolve_region(region)
    return f"{geo} {q}".strip()
