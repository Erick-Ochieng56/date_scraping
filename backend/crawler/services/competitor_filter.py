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
) -> tuple[bool, str]:
    keywords = build_keyword_set(crawl_source)
    domain_lower = (domain or "").lower().strip()

    for pat in _DOMAIN_HARD_BLOCK_PATTERNS:
        if re.search(pat, domain_lower):
            return True, f"Domain matches LSP pattern: /{pat}/"

    for kw in keywords:
        if kw in domain_lower:
            return True, f"Domain contains keyword: '{kw}'"

    combined = " ".join(page_texts)[:5000].lower()
    hits = [kw for kw in keywords if kw in combined]

    # Require more evidence than two weak substrings (buyer pages can mention e.g.
    # "translation" + "localization" in unrelated contexts).
    if len(hits) >= 3:
        return True, f"Content matches keywords: {hits[:5]}"

    org_lower = (org_type_hint or "").lower().strip()
    for ot in GENERIC_COMPETITOR_ORG_TYPES:
        if ot in org_lower:
            return True, f"Org type matches generic competitor type: {ot}"

    for pat in _ORG_HARD_BLOCK_PATTERNS:
        if re.search(pat, combined) or re.search(pat, org_lower):
            return True, f"Content/org-type matches LSP pattern: /{pat}/"

    if crawl_source and crawl_source.competitor_org_types:
        for ot in crawl_source.competitor_org_types:
            if ot and str(ot).lower() in org_lower:
                return True, f"Org type matches competitor list: {ot}"

    return False, ""
