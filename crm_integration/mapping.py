from __future__ import annotations

from typing import Any

from leads.models import Lead


def build_perfex_lead_payload(lead: Lead, *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Map our Lead model to a Perfex lead payload.

    Perfex REST modules vary slightly; this keeps a conservative, widely-used set
    of fields, and lets env defaults fill in ids like `status`, `source`, etc.
    """
    defaults = defaults or {}

    description_parts = []
    if lead.event_text:
        description_parts.append(f"Event: {lead.event_text}")
    if lead.event_date:
        description_parts.append(f"Event date: {lead.event_date.isoformat()}")
    if lead.event_datetime:
        description_parts.append(f"Event datetime: {lead.event_datetime.isoformat()}")
    if lead.source_url:
        description_parts.append(f"Source URL: {lead.source_url}")
    if lead.notes:
        description_parts.append(lead.notes)

    payload: dict[str, Any] = {
        "name": lead.full_name or "Unknown",
        "email": lead.email or "",
        "phonenumber": lead.phone_e164 or lead.phone_raw or "",
        "company": lead.company or "",
        "description": "\n".join([p for p in description_parts if p]),
    }

    # Allow raw payload to include extra perfex fields (advanced usage)
    extra = {}
    raw_extra = (lead.raw_payload or {}).get("perfex") if isinstance(lead.raw_payload, dict) else None
    if isinstance(raw_extra, dict):
        extra = raw_extra

    payload.update({k: v for k, v in defaults.items() if v is not None and v != ""})
    payload.update(extra)
    return payload

