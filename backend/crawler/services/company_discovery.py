from __future__ import annotations

from datetime import date

from crawler.services.geo_filter import resolve_region

_GOV_TLD_BY_COUNTRY = {
    "kenya": ".go.ke",
    "uganda": ".go.ug",
    "tanzania": ".go.tz",
    "rwanda": ".gov.rw",
    "burundi": ".gov.bi",
    "south sudan": ".gov.ss",
    "ethiopia": ".gov.et",
}


def _government_site_fragment(region: str) -> str:
    """
    Build a `site:<gov-tld>` OR-fragment for whichever East African countries are
    mentioned in the resolved region, instead of hardcoding Kenya's `.go.ke`
    regardless of the selected region (DISCOVERY_QUALITY_ANALYSIS.md F6).
    """
    low = (region or "").lower()
    matched = [tld for country, tld in _GOV_TLD_BY_COUNTRY.items() if country in low]
    if not matched:
        matched = list(_GOV_TLD_BY_COUNTRY.values())
    sites = " OR ".join(f"site:{tld}" for tld in matched)
    return f"({sites})" if len(matched) > 1 else sites


def company_first_query_templates(
    *,
    region: str = "",
    industry: str = "",
    seed: str = "",
) -> list[dict]:
    """
    Search angles aimed at specific buyer opportunities (tenders/RFPs), not org homepages.
    """
    geo = resolve_region(region)
    ind = (industry or "").strip()
    ind_bit = f"{ind} " if ind else ""
    seed_bit = (seed or "").strip()
    seed_suffix = f" {seed_bit}" if seed_bit else ""
    year = date.today().year
    next_year = year + 1

    exclude = (
        "-eventbrite -10times -cvent -allevents -meetup -directory -listing "
        "-filetype:pdf -kenyatenders -tenderimpulse -untalent -unjobs"
    )

    return [
        {
            "query": (
                f'{geo} {ind_bit}inurl:tender "simultaneous interpretation" OR "translation services" '
                f'"closing date" {year} {exclude}'
            ),
            "intent": "Active government/NGO tenders for interpretation or translation",
            "expected_prospect_type": "government",
        },
        {
            "query": (
                f'{geo} {ind_bit}"request for proposal" interpretation OR translation '
                f'deadline {year} OR {next_year} {exclude}'
            ),
            "intent": "Open RFPs with deadlines for language services",
            "expected_prospect_type": "ngo",
        },
        {
            "query": (
                f"{geo} {ind_bit}{_government_site_fragment(geo)} procurement interpretation "
                f"translation tender {year} {exclude}"
            ),
            "intent": "East Africa government procurement notices",
            "expected_prospect_type": "government",
        },
        {
            "query": (
                f"{geo} {ind_bit}hospital \"request for proposal\" patient information translation {year} {exclude}"
            ),
            "intent": "Healthcare translation procurement",
            "expected_prospect_type": "hospital",
        },
        {
            "query": (
                f'{geo} {ind_bit}NGO "invitation to tender" interpretation equipment {year} {exclude}'
            ),
            "intent": "NGO interpretation/equipment tenders",
            "expected_prospect_type": "ngo",
        },
        {
            "query": (
                f'{geo} {ind_bit}university "annual conference" interpretation tender RFP {next_year} {exclude}'
            ),
            "intent": "Universities procuring conference interpretation",
            "expected_prospect_type": "university",
        },
        {
            "query": (
                f'{geo} {ind_bit}law firm "request for proposal" sworn translator cross-border {year} {exclude}'
            ),
            "intent": "Law firm document translation RFPs",
            "expected_prospect_type": "law_firm",
        },
        {
            "query": (
                f'{geo} {ind_bit}"hire interpreter" OR "hiring interpreter" conference {year} OR {next_year} '
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Direct interpreter hiring for events",
            "expected_prospect_type": "corporate",
        },
    ]


def general_prospect_query_templates(
    *,
    region: str = "",
    industry: str = "",
    seed: str = "",
) -> list[dict]:
    """
    Search angles aimed at organizations that plausibly need language services on an
    ongoing basis — international operations, multilingual staff/clients, cross-border
    activity — without requiring a live tender/RFP/hiring signal. Used in general-prospect
    mode (D1: default mode) instead of company_first_query_templates' tender-hunting angles.
    """
    geo = resolve_region(region)
    ind = (industry or "").strip()
    ind_bit = f"{ind} " if ind else ""
    seed_bit = (seed or "").strip()
    seed_suffix = f" {seed_bit}" if seed_bit else ""
    exclude = "-eventbrite -10times -cvent -allevents -meetup -directory -listing -filetype:pdf"

    return [
        {
            "query": f"{geo} {ind_bit}international NGO multilingual programmes{seed_suffix} {exclude}",
            "intent": "NGOs with ongoing multilingual/international operations",
            "expected_prospect_type": "ngo",
        },
        {
            "query": (
                f"{geo} {ind_bit}law firm international clients cross-border transactions"
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Law firms with cross-border/multilingual document needs",
            "expected_prospect_type": "law_firm",
        },
        {
            "query": (
                f"{geo} {ind_bit}hospital international patients multilingual services"
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Healthcare providers serving multilingual/international patients",
            "expected_prospect_type": "hospital",
        },
        {
            "query": (
                f"{geo} {ind_bit}university international students conference multilingual"
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Academic institutions with international programmes",
            "expected_prospect_type": "university",
        },
        {
            "query": f"{geo} {ind_bit}multinational corporation subsidiary office{seed_suffix} {exclude}",
            "intent": "Corporates with cross-border operations needing document/localization support",
            "expected_prospect_type": "corporate",
        },
        {
            "query": f"{geo} {ind_bit}embassy OR diplomatic mission consulate{seed_suffix} {exclude}",
            "intent": "Diplomatic missions with ongoing translation/interpretation needs",
            "expected_prospect_type": "diplomatic",
        },
        {
            "query": (
                f"{geo} {ind_bit}bank OR financial institution international clients multilingual"
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Financial institutions serving international/multilingual clients",
            "expected_prospect_type": "financial",
        },
        {
            "query": (
                f"{geo} {ind_bit}export import manufacturer international trade{seed_suffix} {exclude}"
            ),
            "intent": "Manufacturing/trade companies with cross-border documentation needs",
            "expected_prospect_type": "manufacturing_trade",
        },
        {
            "query": (
                f"{geo} {ind_bit}religious organization faith-based international congregation"
                f"{seed_suffix} {exclude}"
            ),
            "intent": "Faith-based organizations with international congregations",
            "expected_prospect_type": "faith_based",
        },
        {
            "query": f"{geo} {ind_bit}sports federation international tournament{seed_suffix} {exclude}",
            "intent": "Sports federations hosting international events",
            "expected_prospect_type": "sports_federation",
        },
    ]


GENERAL_PROSPECT_GROUNDED_RULES = """
Target INDIVIDUAL organizations (named companies, NGOs, law firms, hospitals,
universities, financial institutions, government bodies, embassies/diplomatic
missions, manufacturers/trade companies, media organizations, religious/faith-based
organizations, sports federations) — not event listing websites — that PLAUSIBLY NEED
translation, interpretation, or localization on an ongoing basis (international
operations, multilingual staff/clients, cross-border activity), even with no live
tender or RFP posted right now.

For each result return a specific organization with:
- org_name: the actual organization name (required when possible)
- contact_email: a general/contact email on their site if visible
- source_url: the most relevant page found (an about/international/programmes page is fine)

EXCLUDE event directories and aggregators (Eventbrite listings, 10times, Cvent browse
pages, generic calendars, tender aggregators). If you only find a directory, skip it.
EXCLUDE translation agencies, LSPs, and freelance marketplaces for linguists only.
"""


COMPANY_FIRST_GROUNDED_RULES = """
Target INDIVIDUAL organizations (named companies, associations, ministries, hospitals,
law firms, universities) — not event listing websites.

For each result return a specific buyer organization with:
- org_name: the actual organization name (required when possible)
- contact_email: procurement/events/contact email on their site if visible
- source_url: the SPECIFIC tender/RFP/event page — NOT the org homepage or careers page

EXCLUDE event directories and aggregators (Eventbrite listings, 10times, Cvent browse
pages, generic calendars, tender aggregators). If you only find a directory, skip it.

ONLY include opportunities with dates on or after today (open tenders, upcoming events).
Skip past conferences, closed tenders, and archived documents.
"""
