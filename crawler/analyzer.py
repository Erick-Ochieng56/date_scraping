from __future__ import annotations

import logging
import re
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


_COUNTRY_REGEX = re.compile(
    r"\b("
    r"africa|nigeria|kenya|ethiopia|ghana|tanzania|uganda|rwanda|south africa|"
    r"united states|usa|united kingdom|uk|france|germany|spain|italy|"
    r"canada|australia|india|china|japan|brazil|mexico"
    r")\b",
    re.I,
)


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
    """Detect country/region mentions as a proxy for international work."""
    t = text or ""
    hits = {m.group(0).strip().lower() for m in _COUNTRY_REGEX.finditer(t)}
    return sorted(hits)


def detect_languages_from_html(html_pages: list[str]) -> list[str]:
    """
    Detect languages from <html lang="..."> attributes.
    Returns a list of normalized language codes (e.g., ['en', 'fr']).
    """
    langs: set[str] = set()
    for html in html_pages:
        for m in re.finditer(r"<html[^>]+lang=['\"]([^'\"]+)['\"]", html or "", flags=re.I):
            code = (m.group(1) or "").strip().lower()
            if not code:
                continue
            # Normalize 'en-US' -> 'en'
            code = code.split("-")[0].split("_")[0]
            if 2 <= len(code) <= 8:
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

