from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from dateutil import parser as date_parser


@dataclass(frozen=True)
class NormalizedPhone:
    raw: str
    e164: str
    country_code: str


def normalize_phone(phone_raw: str, default_region: str | None = None) -> NormalizedPhone | None:
    phone_raw = (phone_raw or "").strip()
    if not phone_raw:
        return None

    try:
        import phonenumbers

        parsed = phonenumbers.parse(phone_raw, default_region or None)
        if not phonenumbers.is_valid_number(parsed):
            return None
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        region = phonenumbers.region_code_for_number(parsed) or ""
        return NormalizedPhone(raw=phone_raw, e164=e164, country_code=region)
    except Exception:
        return None


def parse_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date_parser.parse(value)
    except Exception:
        return None


def parse_date(value: str) -> date | None:
    dt = parse_datetime(value)
    return dt.date() if dt else None

