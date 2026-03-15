from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


SERVICE_KEYWORDS: dict[str, list[str]] = {
    "conference_interpretation": [
        "conference",
        "summit",
        "forum",
        "symposium",
        "workshop",
        "interpreting",
        "interpretation",
        "simultaneous translation",
        "plenary session",
        "multilingual conference",
        "international participants",
        "delegates from",
        "participants from countries",
    ],
    "translation": [
        "translation",
        "multilingual",
        "language services",
        "document translation",
        "certified translation",
        "legal translation",
        "technical translation",
        "content translation",
        "language barrier",
    ],
    "localization": [
        "localization",
        "localisation",
        "website localization",
        "software localization",
        "internationalization",
        "global product",
        "market adaptation",
        "regional content",
        "culturally adapted",
    ],
    "sign_language": [
        "sign language",
        "deaf",
        "hard of hearing",
        "accessibility",
        "inclusive",
        "asl",
        "bsl",
        "sign language interpreter",
    ],
    "rapporteuring": [
        "rapporteur",
        "conference report",
        "meeting minutes",
        "session report",
        "proceedings",
        "official report",
        "documentation",
        "conference documentation",
        "outcome document",
    ],
    "copy_editing": [
        "copy editing",
        "proofreading",
        "academic publishing",
        "manuscript",
        "journal submission",
        "research publication",
        "editorial",
        "language editing",
        "writing services",
    ],
    "conference_equipment": [
        "interpretation booth",
        "pa system",
        "audio equipment",
        "conference equipment",
        "av setup",
        "sound system",
        "conference technology",
        "simultaneous equipment",
    ],
}


ORG_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ngo": [
        "ngo",
        "non-governmental",
        "nonprofit",
        "not for profit",
        "charity",
        "humanitarian",
        "civil society",
    ],
    "university": [
        "university",
        "college",
        "faculty",
        "academic",
        "research institute",
        "higher education",
    ],
    "government": [
        "ministry",
        "department of",
        "government",
        "official",
        "public sector",
        "national authority",
    ],
    "conference": ["conference", "summit", "forum", "symposium"],
    "export_company": ["export", "import", "international trade", "global supply", "cross-border"],
    "development_agency": [
        "development agency",
        "donor",
        "funded by",
        "development programme",
        "bilateral",
    ],
}


_LANG_CODE_RE = re.compile(r"^[a-z]{2,8}$", re.I)


@lru_cache(maxsize=1)
def _country_variant_map() -> dict[str, str]:
    """
    Build a mapping of country name variants -> canonical country name.

    Uses pycountry (already in dependencies) and augments with common abbreviations.
    """
    try:
        import pycountry
    except Exception as exc:  # pragma: no cover
        logger.warning("pycountry not available; falling back to minimal country detection: %s", exc)
        return {
            "usa": "united states",
            "united states": "united states",
            "uk": "united kingdom",
            "united kingdom": "united kingdom",
        }

    variants: dict[str, str] = {}

    def _add(variant: str, canonical: str) -> None:
        v = " ".join((variant or "").strip().lower().split())
        c = " ".join((canonical or "").strip().lower().split())
        if not v or len(v) < 3:
            return
        variants.setdefault(v, c)

    for c in pycountry.countries:
        canonical = getattr(c, "name", "") or ""
        if not canonical:
            continue
        _add(canonical, canonical)
        _add(getattr(c, "official_name", "") or "", canonical)
        _add(getattr(c, "common_name", "") or "", canonical)

        # Add comma-stripped variants (e.g., "Korea, Republic of")
        if "," in canonical:
            _add(canonical.replace(",", ""), canonical)

    # Common abbreviations / aliases
    aliases = {
        "u.s.": "united states",
        "u.s.a.": "united states",
        "us": "united states",
        "usa": "united states",
        "united states of america": "united states",
        "u.k.": "united kingdom",
        "uk": "united kingdom",
        "great britain": "united kingdom",
        "ivory coast": "côte d'ivoire",
        "cote d'ivoire": "côte d'ivoire",
        "cote d ivoire": "côte d'ivoire",
        "uae": "united arab emirates",
        "u.a.e.": "united arab emirates",
        "drc": "congo, the democratic republic of the",
        "dr congo": "congo, the democratic republic of the",
    }
    for k, v in aliases.items():
        _add(k, v)

    return variants


@lru_cache(maxsize=1)
def _country_regex() -> re.Pattern[str]:
    """
    One big regex to match any known country name variant.
    """
    variants = list(_country_variant_map().keys())
    # Longest first avoids partial matches stealing earlier.
    variants.sort(key=len, reverse=True)
    escaped = [re.escape(v) for v in variants if v]
    # Use non-capturing group; allow whitespace flexibility inside multiword names.
    # We pre-normalize input whitespace, so plain escaped spaces are fine.
    return re.compile(r"\b(?:%s)\b" % "|".join(escaped), re.I)


def detect_services(text: str) -> list[str]:
    """Detect which Ateric services are indicated by website text."""
    t = (text or "").lower()
    detected: list[str] = []
    for service, keywords in SERVICE_KEYWORDS.items():
        if any(k.lower() in t for k in keywords):
            detected.append(service)
    return detected


def detect_org_types(text: str) -> list[str]:
    """Detect likely organization types from website text."""
    t = (text or "").lower()
    detected: list[str] = []
    for org_type, keywords in ORG_TYPE_KEYWORDS.items():
        if any(k.lower() in t for k in keywords):
            detected.append(org_type)
    return detected


def detect_countries(text: str) -> list[str]:
    """
    Detect country mentions as a proxy for international work.

    Returns a list of canonical country names (lowercase).
    """
    t = " ".join((text or "").split())
    if not t:
        return []

    mapping = _country_variant_map()
    rx = _country_regex()
    hits: set[str] = set()
    for m in rx.finditer(t):
        raw = " ".join(m.group(0).strip().lower().split())
        canonical = mapping.get(raw, raw)
        if canonical:
            hits.add(canonical)
        if len(hits) >= 25:
            break
    return sorted(hits)


def detect_languages_from_html(html_pages: list[str]) -> list[str]:
    """
    Detect languages from common HTML signals:
    - <html lang="...">
    - <link rel="alternate" hreflang="...">
    - <meta property="og:locale" content="en_US">
    - <meta name="language" content="en">

    Returns a list of normalized language codes (e.g., ['en', 'fr']).
    """
    langs: set[str] = set()
    for html in html_pages:
        h = html or ""

        # <html lang="">
        for m in re.finditer(r"<html[^>]+lang=['\"]([^'\"]+)['\"]", h, flags=re.I):
            code = (m.group(1) or "").strip().lower()
            code = code.split("-")[0].split("_")[0]
            if _LANG_CODE_RE.match(code or ""):
                langs.add(code)

        # hreflang values on alternate links
        for m in re.finditer(r"hreflang=['\"]([^'\"]+)['\"]", h, flags=re.I):
            code = (m.group(1) or "").strip().lower()
            if code in {"x-default", "default"}:
                continue
            code = code.split("-")[0].split("_")[0]
            if _LANG_CODE_RE.match(code or ""):
                langs.add(code)

        # OpenGraph locale
        for m in re.finditer(
            r"<meta[^>]+property=['\"]og:locale['\"][^>]+content=['\"]([^'\"]+)['\"]",
            h,
            flags=re.I,
        ):
            code = (m.group(1) or "").strip().lower()
            code = code.split("-")[0].split("_")[0]
            if _LANG_CODE_RE.match(code or ""):
                langs.add(code)

        # <meta name="language" content="en">
        for m in re.finditer(
            r"<meta[^>]+name=['\"]language['\"][^>]+content=['\"]([^'\"]+)['\"]",
            h,
            flags=re.I,
        ):
            code = (m.group(1) or "").strip().lower()
            code = code.split("-")[0].split("_")[0]
            if _LANG_CODE_RE.match(code or ""):
                langs.add(code)
    return sorted(langs)


def build_international_signals(text: str) -> list[str]:
    """Return a list of human-readable international signals found in text."""
    t = (text or "").lower()
    signals: list[str] = []
    if "international participants" in t or "participants from" in t or "delegates from" in t:
        signals.append("international_participants")
    if "multilingual" in t or "multiple languages" in t:
        signals.append("multilingual")
    if "global" in t or "international" in t:
        signals.append("global_international_mentions")
    return signals

