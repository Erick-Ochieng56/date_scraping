from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Iterable
from urllib.parse import urlparse

import phonenumbers

from crawler.constants import EMAIL_REGEX

logger = logging.getLogger(__name__)


def extract_emails(text: str) -> list[str]:
    """
    Extract emails, filter out common false positives.
    """
    candidates = re.findall(EMAIL_REGEX, text or "")
    out: list[str] = []
    for e in candidates:
        el = e.strip().lower()
        # Filter common asset-like endings
        if el.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js")):
            continue
        if el.count("@") != 1:
            continue
        if el not in out:
            out.append(el)
    return out


def extract_phones(text: str) -> list[str]:
    """
    Extract phone numbers and normalize to E.164 format.
    Uses phonenumbers for international formats.
    """
    t = text or ""
    out: list[str] = []
    try:
        for match in phonenumbers.PhoneNumberMatcher(t, None):
            num = match.number
            if not phonenumbers.is_possible_number(num):
                continue
            if not phonenumbers.is_valid_number(num):
                continue
            e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
            if e164 not in out:
                out.append(e164)
    except Exception as exc:
        logger.debug("phone extraction failed: %s", exc)
    return out


@lru_cache(maxsize=1)
def _spacy_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception as exc:
        logger.warning("spaCy model not available (en_core_web_sm): %s", exc)
        return None


def extract_org_name(text: str, domain: str) -> str:
    """
    Extract organization name using spaCy NER.
    Fallback: derive from domain hostname.
    """
    t = (text or "").strip()
    nlp = _spacy_nlp()
    if nlp and t:
        doc = nlp(t[:5000])
        orgs = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
        if orgs:
            # Prefer the longest org mention
            orgs.sort(key=len, reverse=True)
            return orgs[0][:255]

    host = urlparse(domain).netloc or domain
    host = host.lower().replace("www.", "")
    base = host.split(":")[0].split(".")[0]
    return (base.replace("-", " ").replace("_", " ").title())[:255]


_EVENT_PATTERNS = [
    r"\bGlobal\s+[\w\s]{2,60}\s+(Summit|Conference|Forum)\s+(20\d{2})\b",
    r"\bAnnual\s+[\w\s]{2,60}\s+(Symposium|Conference|Forum)\b",
    r"\b[\w\s]{2,60}\s+(Summit|Conference|Forum|Symposium|Workshop)\s+(20\d{2})\b",
]


def extract_event_names(text: str) -> list[str]:
    """
    Detect event names using regex patterns and (optionally) spaCy entities.
    """
    t = (text or "").strip()
    out: list[str] = []

    for pat in _EVENT_PATTERNS:
        for m in re.finditer(pat, t, flags=re.IGNORECASE):
            name = " ".join(m.group(0).split())
            if name and name not in out:
                out.append(name[:255])
            if len(out) >= 10:
                return out

    nlp = _spacy_nlp()
    if nlp and t and len(out) < 5:
        doc = nlp(t[:5000])
        # Heuristic: event names often appear as ORG or WORK_OF_ART around "conference/summit"
        for sent in doc.sents:
            if re.search(r"\b(conference|summit|forum|symposium|workshop)\b", sent.text, re.I):
                chunk = " ".join(sent.text.split())
                if chunk and chunk not in out:
                    out.append(chunk[:255])
                if len(out) >= 10:
                    break

    return out

