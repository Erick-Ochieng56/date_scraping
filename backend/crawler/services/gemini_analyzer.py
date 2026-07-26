from __future__ import annotations

import json
import logging
import textwrap
import time

from django.conf import settings

from crawler.services.gemini_client import generate_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a lead qualification assistant for a Language Service Provider (LSP).
    Your job is to analyze a company website and determine how likely they need
    professional translation, localization, or interpretation services.

    IMPORTANT: If the website IS itself a translation agency, LSP, language services
    company, localization vendor, or interpretation provider — set is_competitor to true
    and translation_need_score to 0. These are NOT prospects.

    Return ONLY valid JSON — no markdown, no explanation.
"""
)

ANALYSIS_SCHEMA = {
    "org_name": "string — company name or empty string",
    "org_type": "string — best single category e.g. NGO, law_firm, ecommerce, healthcare, tech, event_organizer, government, other",
    "detected_org_types": ["list of org type strings"],
    "detected_services": ["services the company offers"],
    "languages_detected": ["ISO 639-1 codes found on the site e.g. en, fr, sw"],
    "countries_detected": ["country names mentioned"],
    "international_signals": ["evidence of international activity"],
    "contact_emails": ["emails found"],
    "contact_phones": ["phone numbers found"],
    "is_competitor": "boolean — true if this site is itself a translation/LSP company",
    "is_competitor_reason": "string — why you flagged it as competitor or empty string",
    "translation_need_score": "integer 0-100 (always 0 if is_competitor is true)",
    "translation_need_reasoning": "1-2 sentence explanation of the score",
}


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s[: s.rfind("```")].strip()
    return s


def analyze_domain(domain: str, page_texts: list[str]) -> dict:
    combined = "\n\n---\n\n".join(page_texts)[:30_000]
    model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")

    prompt = f"""{SYSTEM_PROMPT}

Domain: {domain}

Website content:
{combined}

Expected JSON schema:
{json.dumps(ANALYSIS_SCHEMA, indent=2)}

Scoring guide for translation_need_score:
- 80-100: Clear international operations, multilingual content needs, NGO/legal/medical
- 60-79: Regional expansion signals, some multilingual mentions
- 40-59: Domestic but growing, niche industries that often need translation
- 20-39: Mostly local, little international signal
- 0-19: No translation need detected

Return the JSON object now:"""

    raw_text = generate_text(model=model_name, prompt=prompt)
    raw = _strip_code_fence(raw_text)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Gemini JSON parse failed for domain=%s", domain)
        return {
            "org_name": "",
            "org_type": "other",
            "detected_org_types": [],
            "detected_services": [],
            "languages_detected": [],
            "countries_detected": [],
            "international_signals": [],
            "contact_emails": [],
            "contact_phones": [],
            "is_competitor": False,
            "is_competitor_reason": "",
            "translation_need_score": 0,
            "translation_need_reasoning": "Parse error",
        }


def analyze_domain_safe(domain: str, page_texts: list[str], retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            return analyze_domain(domain, page_texts)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                time.sleep(2**attempt)
                continue
            if attempt == retries - 1:
                logger.exception("Gemini analyze_domain failed for %s", domain)
                return {
                    "translation_need_score": 0,
                    "is_competitor": False,
                    "is_competitor_reason": "",
                    "org_name": "",
                    "org_type": "other",
                    "detected_org_types": [],
                    "detected_services": [],
                    "languages_detected": [],
                    "countries_detected": [],
                    "international_signals": [],
                    "contact_emails": [],
                    "contact_phones": [],
                    "translation_need_reasoning": err[:200],
                }
            time.sleep(1)
    return {"translation_need_score": 0, "is_competitor": False}
