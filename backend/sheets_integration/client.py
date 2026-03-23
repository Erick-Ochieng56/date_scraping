from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def _load_credentials() -> Credentials:
    """
    Load Google service account credentials from either:
    - GSHEETS_CREDENTIALS_FILE: path to JSON key file
    - GSHEETS_CREDENTIALS_JSON: JSON string with credentials
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    path = _get_env("GSHEETS_CREDENTIALS_FILE")
    if path:
        return Credentials.from_service_account_file(path, scopes=scopes)

    raw_json = _get_env("GSHEETS_CREDENTIALS_JSON")
    if raw_json:
        data: Any = json.loads(raw_json)
        return Credentials.from_service_account_info(data, scopes=scopes)

    raise RuntimeError(
        "Google Sheets credentials missing. Set GSHEETS_CREDENTIALS_FILE or GSHEETS_CREDENTIALS_JSON."
    )


def get_sheets_service():
    creds = _load_credentials()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

