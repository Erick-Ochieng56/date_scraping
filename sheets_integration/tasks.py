from __future__ import annotations

import os

from celery import shared_task

from leads.models import Lead
from sheets_integration.client import get_sheets_service
from sheets_integration.rows import lead_to_row


def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def _get_bool(name: str, default: bool = False) -> bool:
    v = _get_env(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


@shared_task
def append_lead_to_sheet(lead_id: int) -> None:
    if not _get_bool("GSHEETS_ENABLED", default=True):
        return

    spreadsheet_id = _get_env("GSHEETS_SPREADSHEET_ID")
    value_range = _get_env("GSHEETS_LEADS_RANGE", "Leads!A:Z")
    if not spreadsheet_id:
        # Misconfigured; nothing to do.
        return

    lead = Lead.objects.get(id=lead_id)
    service = get_sheets_service()
    body = {"values": [lead_to_row(lead)]}
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=value_range,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

