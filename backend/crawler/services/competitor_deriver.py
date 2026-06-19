from __future__ import annotations

import json
import logging
import time

from django.conf import settings

from crawler.services.gemini_client import generate_text

logger = logging.getLogger(__name__)

_FALLBACK_SIGNALS = {
    "competitor_keywords": ["translation agency", "language service provider", "localization vendor"],
    "competitor_org_types": ["translation_agency", "lsp", "localization_vendor"],
    "prospect_org_types": [],
    "prospect_signals": [],
    "reasoning": "Fallback defaults",
}


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s[: s.rfind("```")].strip()
    return s


def derive_competitor_signals(discovery_query: str) -> dict:
    model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")
    prompt = f"""
You are helping configure a lead generation crawler for a Language Service Provider (LSP).

The crawler uses this search query to find prospects:
"{discovery_query}"

Your job: determine what a COMPETITOR website would look like vs what a PROSPECT looks like,
so we can filter out competitors automatically.

Return ONLY valid JSON with this schema:
{{
    "competitor_keywords": [
        "keywords/phrases that appear on competitor LSP/translation company websites"
    ],
    "competitor_org_types": [
        "org type labels for competitors e.g. translation_agency, lsp, localization_vendor"
    ],
    "prospect_org_types": [
        "org type labels for ideal prospects e.g. law_firm, ngo, hospital, ecommerce_brand"
    ],
    "prospect_signals": [
        "phrases that indicate a site NEEDS translation but is not a translation company"
    ],
    "reasoning": "brief explanation of the distinction for this query"
}}
"""


    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            raw_text = generate_text(model=model_name, prompt=prompt)
            break
        except Exception as exc:
            last_exc = exc
            err = str(exc)
            if ("429" in err or "RESOURCE_EXHAUSTED" in err) and attempt == 0:
                time.sleep(3)
                continue
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                logger.warning("derive_competitor_signals rate limited; using fallback defaults")
                return dict(_FALLBACK_SIGNALS)
            raise
    else:
        if last_exc is not None:
            raise last_exc
        raw_text = ""

    raw = _strip_code_fence(raw_text)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("derive_competitor_signals parse failed")
        return {
            "competitor_keywords": ["translation", "localization", "language service"],
            "competitor_org_types": ["translation_agency", "lsp"],
            "prospect_org_types": [],
            "prospect_signals": [],
            "reasoning": "Fallback defaults — parse error",
        }
