from __future__ import annotations

from crawler.models import EventProspect
from crawler.scoring import get_score_label
from crawler.utils import compute_payload_hash, normalize_domain_url
from leads.models import Prospect, ProspectStatus


def promote_event_prospect_to_prospect(
    event_prospect: EventProspect,
) -> tuple[Prospect, bool]:
    """
    Create a Prospect from an EventProspect and mark the event row converted.
    """
    if event_prospect.status == "converted":
        existing = Prospect.objects.filter(
            source_name="event_crawler",
            event_name=event_prospect.event_name,
            website__icontains=event_prospect.organizer_domain,
        ).order_by("-id").first()
        if existing:
            return existing, False

    organizer_domain = (event_prospect.organizer_domain or "").strip().lower().removeprefix("www.")
    website = normalize_domain_url(organizer_domain) if organizer_domain else ""
    event_url = (event_prospect.event_url or "").strip()
    source_url = event_url or website

    email = (event_prospect.contact_email or "").strip() or None
    phone = (event_prospect.contact_phone or "").strip()
    company = (event_prospect.organizer_name or "").strip() or organizer_domain or "Unknown organizer"

    score = int(event_prospect.translation_need_score or 0)
    payload = {
        "source": "event_crawler",
        "event_prospect_id": event_prospect.id,
        "event_name": event_prospect.event_name,
        "event_type": event_prospect.event_type,
        "event_date": event_prospect.event_date.isoformat() if event_prospect.event_date else "",
        "event_location": event_prospect.event_location,
        "languages_involved": event_prospect.languages_involved or [],
        "countries_involved": event_prospect.countries_involved or [],
        "translation_services_needed": event_prospect.translation_services_needed or [],
        "translation_need_score": score,
        "urgency_score": event_prospect.urgency_score,
        "score_label": get_score_label(score),
        "is_virtual": event_prospect.is_virtual,
        "is_hybrid": event_prospect.is_hybrid,
    }
    payload_hash = compute_payload_hash(payload)

    qs = Prospect.objects.filter(owner=event_prospect.owner)
    existing = None
    if email:
        existing = qs.filter(email__iexact=email).first()
    if not existing and website:
        existing = qs.filter(website=website).first()
    if not existing:
        existing = qs.filter(raw_payload_hash=payload_hash).first()

    notes_parts = []
    if event_prospect.notes:
        notes_parts.append(event_prospect.notes.strip())
    if event_prospect.translation_services_needed:
        services = ", ".join(str(s) for s in event_prospect.translation_services_needed[:8])
        notes_parts.append(f"Translation services: {services}")
    if event_prospect.languages_involved:
        langs = ", ".join(str(s) for s in event_prospect.languages_involved[:8])
        notes_parts.append(f"Languages: {langs}")
    notes = "\n".join(notes_parts)[:2000]

    if existing:
        event_prospect.status = "converted"
        event_prospect.save(update_fields=["status", "updated_at"])
        return existing, False

    prospect = Prospect.objects.create(
        owner=event_prospect.owner,
        source_name="event_crawler",
        source_url=source_url[:2000] if source_url else "",
        company=company[:255],
        email=email,
        phone_raw=phone,
        phone_e164=phone,
        website=website,
        event_name=event_prospect.event_name[:255],
        raw_payload=payload,
        raw_payload_hash=payload_hash,
        status=ProspectStatus.NEW,
        notes=notes,
    )
    event_prospect.status = "converted"
    event_prospect.save(update_fields=["status", "updated_at"])
    return prospect, True
