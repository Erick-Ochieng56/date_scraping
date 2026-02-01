from __future__ import annotations

from typing import List

from leads.models import Lead


def lead_to_row(lead: Lead) -> List[str]:
    """
    Map a Lead to a flat row suitable for a Google Sheet.
    
    Columns match Perfex CRM fields for easy manual import:
    ID, Status, Created, Updated, Name, Position, Email, Website, Phone,
    Company, Address, City, State, Country, Zip, Language, Lead Value,
    Event Date, Event DateTime, Event Text, Source Name, Source URL, Notes
    """
    return [
        str(lead.id),
        lead.status,
        lead.created_at.isoformat() if lead.created_at else "",
        lead.updated_at.isoformat() if lead.updated_at else "",
        lead.full_name or "",
        lead.position or "",
        lead.email or "",
        lead.website or "",
        lead.phone_e164 or lead.phone_raw or "",
        lead.company or "",
        lead.address or "",
        lead.city or "",
        lead.state or "",
        lead.country_code or "",
        lead.zip_code or "",
        lead.default_language or "",
        str(lead.lead_value) if lead.lead_value else "",
        lead.event_date.isoformat() if lead.event_date else "",
        lead.event_datetime.isoformat() if lead.event_datetime else "",
        lead.event_text or "",
        lead.source_name or "",
        lead.source_url or "",
        lead.source_ref or "",
        lead.notes or "",
    ]

