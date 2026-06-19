from __future__ import annotations

import re

from crawler.models import CrawlSource

# Vendor / LSP signals. Avoid generic phrases ("interpretation services") that also
# appear on conference buyer and RFP pages — those caused false positives for prospects.
BASE_COMPETITOR_KEYWORDS = [
    "translation agency",
    "language service provider",
    "lsp",
    "localization vendor",
    "sworn translator",
    "certified translator",
    "we translate",
    "our translators",
    "translation company",
    "language pair",
    "language solutions",
    "translation bureau",
    "language bureau",
]

_LSP_SELLER_PHRASES = (
    "we offer translation",
    "we provide interpretation",
    "we provide translation",
    "our team of translators",
    "our interpreters",
    "language services company",
    "certified translators",
    "professional translation services",
    "hire our linguists",
)

GENERIC_COMPETITOR_ORG_TYPES = {
    "translation_agency",
    "lsp",
    "language_service_provider",
    "localization_vendor",
    "translation_company",
    "interpreting_agency",
}

_DOMAIN_HARD_BLOCK_PATTERNS = (
    r"translat(?:e|ion|or)",
    r"locali[sz](?:e|ation)",
    r"interpret(?:er|ing|ation)",
    r"language[-_]?services?",
    r"\blsp\b",
)

_ORG_HARD_BLOCK_PATTERNS = (
    r"\btranslation (agency|company|bureau|services?)\b",
    r"\blanguage service provider\b",
    r"\blocali[sz]ation (agency|company|vendor)\b",
    r"\binterpret(?:ing|ation) (agency|company|services?)\b",
)


def build_keyword_set(crawl_source: CrawlSource | None) -> list[str]:
    if not crawl_source:
        return list(BASE_COMPETITOR_KEYWORDS)
    source_keywords = crawl_source.competitor_keywords or []
    return list(set(BASE_COMPETITOR_KEYWORDS + list(source_keywords)))


def is_likely_competitor(
    domain: str,
    page_texts: list[str],
    crawl_source: CrawlSource | None = None,
    org_type_hint: str = "",
    landing_url: str = "",
) -> tuple[bool, str]:
    from crawler.services.active_buyer import is_buyer_procurement_context

    keywords = build_keyword_set(crawl_source)
    domain_lower = (domain or "").lower().strip()

    for pat in _DOMAIN_HARD_BLOCK_PATTERNS:
        if re.search(pat, domain_lower):
            return True, f"Domain matches LSP pattern: /{pat}/"

    for kw in keywords:
        if kw in domain_lower:
            return True, f"Domain contains keyword: '{kw}'"

    combined = " ".join(page_texts)[:8000].lower()
    buyer_context = is_buyer_procurement_context(combined)

    hits = [kw for kw in keywords if kw in combined]

    seller_hits = [p for p in _LSP_SELLER_PHRASES if p in combined]
    if len(seller_hits) >= 1 and len(hits) >= 1:
        return True, f"Content matches LSP seller signals: {seller_hits[:3]}"

    if len(hits) >= 3:
        return True, f"Content matches keywords: {hits[:5]}"

    org_lower = (org_type_hint or "").lower().strip()
    for ot in GENERIC_COMPETITOR_ORG_TYPES:
        if ot in org_lower:
            return True, f"Org type matches generic competitor type: {ot}"

    if not buyer_context:
        for pat in _ORG_HARD_BLOCK_PATTERNS:
            if re.search(pat, combined) or re.search(pat, org_lower):
                return True, f"Content/org-type matches LSP pattern: /{pat}/"

    if crawl_source and crawl_source.competitor_org_types:
        for ot in crawl_source.competitor_org_types:
            if ot and str(ot).lower() in org_lower:
                return True, f"Org type matches competitor list: {ot}"

    return False, ""
