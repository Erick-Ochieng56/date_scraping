from __future__ import annotations

from django.db.models import Q

from leads.models import Lead, Prospect


def _prospect_match_reason(prospect: Prospect, other: Prospect) -> str:
    if prospect.raw_payload_hash and other.raw_payload_hash == prospect.raw_payload_hash:
        return "same_payload_hash"
    if prospect.email and other.email and prospect.email.lower() == other.email.lower():
        return "same_email"
    if prospect.website and other.website and prospect.website.rstrip("/") == other.website.rstrip("/"):
        return "same_website"
    return "similar"


def find_prospect_duplicates(prospect: Prospect, base_qs) -> list[dict]:
    """Return other prospects that likely duplicate this record (same owner scope)."""
    qs = base_qs.exclude(id=prospect.id)
    filters = Q()
    if prospect.raw_payload_hash:
        filters |= Q(raw_payload_hash=prospect.raw_payload_hash)
    if prospect.email:
        filters |= Q(email__iexact=prospect.email)
    if prospect.website:
        filters |= Q(website=prospect.website)
    if not filters:
        return []

    seen: set[int] = set()
    rows: list[dict] = []
    for other in qs.filter(filters).order_by("-updated_at")[:10]:
        if other.id in seen:
            continue
        seen.add(other.id)
        rows.append(
            {
                "id": other.id,
                "company": other.company,
                "email": other.email,
                "website": other.website,
                "status": other.status,
                "match_reason": _prospect_match_reason(prospect, other),
                "created_at": other.created_at.isoformat() if other.created_at else None,
            }
        )
    return rows


def find_lead_duplicates(lead: Lead, base_qs) -> list[dict]:
    qs = base_qs.exclude(id=lead.id)
    filters = Q()
    if lead.raw_payload_hash:
        filters |= Q(raw_payload_hash=lead.raw_payload_hash)
    if lead.email:
        filters |= Q(email__iexact=lead.email)
    if lead.website:
        filters |= Q(website=lead.website)
    if lead.prospect_id:
        filters |= Q(prospect_id=lead.prospect_id)
    if not filters:
        return []

    seen: set[int] = set()
    rows: list[dict] = []
    for other in qs.filter(filters).order_by("-updated_at")[:10]:
        if other.id in seen:
            continue
        seen.add(other.id)
        reason = "similar"
        if lead.raw_payload_hash and other.raw_payload_hash == lead.raw_payload_hash:
            reason = "same_payload_hash"
        elif lead.email and other.email and lead.email.lower() == other.email.lower():
            reason = "same_email"
        elif lead.website and other.website == lead.website:
            reason = "same_website"
        elif lead.prospect_id and other.prospect_id == lead.prospect_id:
            reason = "same_prospect"
        rows.append(
            {
                "id": other.id,
                "company": other.company,
                "full_name": other.full_name,
                "email": other.email,
                "status": other.status,
                "match_reason": reason,
                "created_at": other.created_at.isoformat() if other.created_at else None,
            }
        )
    return rows
