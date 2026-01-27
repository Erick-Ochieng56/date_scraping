from __future__ import annotations

from typing import List

from leads.models import Lead


def lead_to_row(lead: Lead) -> List[str]:
    """
    Map a Lead to a flat row suitable for a Google Sheet.

    Adjust as needed to match your Sheet's columns.
    """
    return [
        str(lead.id),
        lead.status,
        lead.created_at.isoformat() if lead.created_at else "",
        lead.updated_at.isoformat() if lead.updated_at else "",
        lead.full_name,
        lead.email or "",
        lead.phone_e164 or lead.phone_raw or "",
        lead.company or "",
        lead.country_code or "",
        lead.source_name or "",
        lead.source_url or "",
        lead.source_ref or "",
        lead.event_date.isoformat() if lead.event_date else "",
        lead.event_datetime.isoformat() if lead.event_datetime else "",
        lead.event_text or "",
    ]

