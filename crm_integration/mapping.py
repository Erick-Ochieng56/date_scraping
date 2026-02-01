from __future__ import annotations

from typing import Any

from leads.models import Lead


def build_perfex_lead_payload(lead: Lead, *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Map our Lead model to a Perfex lead payload for aterictranslation.com.
    
    Maps all Perfex CRM fields including:
    - Status, Source, Assigned (via defaults)
    - Name, Position, Email, Website, Phone
    - Company, Address, City, State, Country, Zip Code
    - Default Language, Lead Value, Description
    - Tags (via raw_payload.perfex.tags)
    """
    defaults = defaults or {}

    # Build description with event information (important for translation events)
    description_parts = []
    if lead.event_text:
        description_parts.append(f"Event: {lead.event_text}")
    if lead.event_date:
        description_parts.append(f"Event Date: {lead.event_date.isoformat()}")
    if lead.event_datetime:
        description_parts.append(f"Event DateTime: {lead.event_datetime.isoformat()}")
    if lead.source_name:
        description_parts.append(f"Source: {lead.source_name}")
    if lead.source_url:
        description_parts.append(f"Source URL: {lead.source_url}")
    if lead.position:
        description_parts.append(f"Position: {lead.position}")
    if lead.default_language:
        description_parts.append(f"Default Language: {lead.default_language}")
    if lead.notes:
        description_parts.append(lead.notes)

    # Build base payload with all standard Perfex fields
    payload: dict[str, Any] = {
        "name": lead.full_name or "Unknown",
        "email": lead.email or "",
        "phonenumber": lead.phone_e164 or lead.phone_raw or "",
        "company": lead.company or "",
        "description": "\n".join([p for p in description_parts if p]),
    }
    
    # Add optional fields if they have values
    if lead.website:
        payload["website"] = lead.website
    if lead.position:
        payload["title"] = lead.position  # Perfex uses "title" for position
    if lead.address:
        payload["address"] = lead.address
    if lead.city:
        payload["city"] = lead.city
    if lead.state:
        payload["state"] = lead.state
    if lead.country_code:
        payload["country"] = lead.country_code
    if lead.zip_code:
        payload["zip"] = lead.zip_code
    if lead.default_language:
        payload["default_language"] = lead.default_language
    if lead.lead_value is not None:
        payload["lead_value"] = float(lead.lead_value)

    # Allow raw payload to include extra perfex fields (tags, assigned, etc.)
    extra = {}
    raw_extra = (lead.raw_payload or {}).get("perfex") if isinstance(lead.raw_payload, dict) else None
    if isinstance(raw_extra, dict):
        extra = raw_extra

    # Apply defaults (status, source, assigned, etc.) - these override empty values
    payload.update({k: v for k, v in defaults.items() if v is not None and v != ""})
    
    # Apply extra fields from raw_payload (tags, custom fields, etc.)
    payload.update(extra)
    
    return payload

