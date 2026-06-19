from __future__ import annotations

from datetime import date

from crawler.services.geo_filter import resolve_region


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
                f"{geo} {ind_bit}site:.go.ke procurement interpretation translation tender {year} {exclude}"
            ),
            "intent": "Kenya government procurement notices",
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
