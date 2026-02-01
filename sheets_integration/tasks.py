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


def _extract_spreadsheet_id(url_or_id: str) -> str:
    """
    Extract spreadsheet ID from a Google Sheets URL or return as-is if already an ID.
    
    Handles formats like:
    - https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit...
    - SPREADSHEET_ID (already an ID)
    """
    if not url_or_id:
        return ""
    
    # If it looks like a URL, extract the ID
    if "/spreadsheets/d/" in url_or_id:
        # Extract ID from URL pattern: .../spreadsheets/d/ID/edit...
        parts = url_or_id.split("/spreadsheets/d/")
        if len(parts) > 1:
            id_part = parts[1].split("/")[0].split("?")[0].split("#")[0]
            return id_part.strip()
    
    # If it's already an ID (alphanumeric, no slashes), return as-is
    return url_or_id.strip()


def _ensure_sheet_exists(service, spreadsheet_id: str, sheet_name: str) -> bool:
    """
    Ensure a sheet tab exists in the spreadsheet. Create it if it doesn't.
    Returns True if sheet exists or was created successfully, False otherwise.
    """
    try:
        # Get spreadsheet metadata
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_names = [sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])]
        
        # If sheet doesn't exist, create it
        if sheet_name not in sheet_names:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Creating sheet '{sheet_name}' in spreadsheet {spreadsheet_id}")
            
            requests = [{
                "addSheet": {
                    "properties": {
                        "title": sheet_name
                    }
                }
            }]
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            logger.info(f"Successfully created sheet '{sheet_name}'")
            return True
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Could not ensure sheet '{sheet_name}' exists: {e}")
        return False


def _extract_sheet_name(range_str: str) -> str:
    """
    Extract sheet name from A1 notation range.
    Examples: "Leads!A:Z" -> "Leads", "Sheet1!A1" -> "Sheet1", "A:Z" -> None
    """
    if "!" in range_str:
        return range_str.split("!")[0]
    return None


@shared_task
def append_lead_to_sheet(lead_id: int) -> None:
    if not _get_bool("GSHEETS_ENABLED", default=True):
        return

    raw_spreadsheet_id = _get_env("GSHEETS_SPREADSHEET_ID")
    if not raw_spreadsheet_id:
        # Misconfigured; nothing to do.
        return
    
    spreadsheet_id = _extract_spreadsheet_id(raw_spreadsheet_id)
    if not spreadsheet_id:
        return
    
    value_range = _get_env("GSHEETS_LEADS_RANGE", "Leads!A:Z")
    
    try:
        lead = Lead.objects.get(id=lead_id)
        service = get_sheets_service()
        
        # Extract sheet name and ensure it exists
        sheet_name = _extract_sheet_name(value_range)
        if not sheet_name:
            # If no sheet name in range, default to "Leads"
            sheet_name = "Leads"
            value_range = "Leads!A:A"  # Use A:A for append (will auto-expand)
        
        # Ensure sheet exists
        sheet_exists = _ensure_sheet_exists(service, spreadsheet_id, sheet_name)
        if not sheet_exists:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Cannot append lead {lead_id}: Sheet '{sheet_name}' does not exist "
                f"and could not be created. Please create it manually in the spreadsheet."
            )
            return
        
        # For append operations, use just the sheet name or a simple range
        # "A:Z" ranges can cause parsing errors, so use "A:A" or just sheet name
        if "!A:Z" in value_range.upper():
            # Replace A:Z with A:A for append (Google Sheets will auto-expand columns)
            append_range = f"{sheet_name}!A:A"
        elif "!" in value_range:
            # Use the provided range as-is
            append_range = value_range
        else:
            # Just sheet name - will append to first available row
            append_range = f"{sheet_name}!"
        
        body = {"values": [lead_to_row(lead)]}
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=append_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        error_msg = str(e)
        
        # Provide helpful error messages for common issues
        if "Unable to parse range" in error_msg or "Requested entity was not found" in error_msg:
            sheet_name = _extract_sheet_name(value_range) or "the specified sheet"
            logger.error(
                f"Failed to append lead {lead_id} to Google Sheets: "
                f"Sheet '{sheet_name}' may not exist. "
                f"Please create a sheet tab named '{sheet_name}' in your spreadsheet, "
                f"or update GSHEETS_LEADS_RANGE to use an existing sheet name."
            )
        else:
            logger.error(f"Failed to append lead {lead_id} to Google Sheets: {e}")
        
        # Don't raise - we don't want to retry indefinitely for configuration errors
        # The error is logged, and the lead will remain in the database

