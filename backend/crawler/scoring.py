from __future__ import annotations

from crawler.models import WebsiteProfile


def score_website(profile: WebsiteProfile) -> int:
    """
    Calculate translation lead score from WebsiteProfile.
    Returns integer 0-100.
    Only call prospect_pipeline if score > 40.
    """
    score = 0

    org_types = set((profile.detected_org_types or []))
    services = set((profile.detected_services or []))
    langs = list(profile.languages_detected or [])
    countries = list(profile.countries_detected or [])
    emails = list(profile.contact_emails or [])
    events = list(profile.event_names or [])
    signals = set(profile.international_signals or [])

    # Org type / context signals
    if "conference" in org_types:
        score += 40
    if "ngo" in org_types or "development_agency" in org_types:
        score += 20
    if "university" in org_types:
        score += 15
    if "government" in org_types:
        score += 20
    if "export_company" in org_types:
        score += 15

    # Service signals
    if "conference_interpretation" in services:
        score += 20
    if "rapporteuring" in services:
        score += 20
    if "sign_language" in services:
        score += 15
    if "copy_editing" in services:
        score += 15
    if "translation" in services:
        score += 10
    if "localization" in services:
        score += 10
    if "conference_equipment" in services:
        score += 10

    # Internationality
    if "international_participants" in signals:
        score += 25
    if len(countries) >= 2:
        score += 20

    # Localization opportunity heuristic
    if len(langs) == 1:
        score += 15

    # Actionability
    if emails:
        score += 5
    if events:
        score += 10

    return max(0, min(100, int(score)))


def get_score_label(score: int) -> str:
    """Returns 'low', 'medium', or 'high' based on score."""
    if score <= 30:
        return "low"
    if score <= 60:
        return "medium"
    return "high"

