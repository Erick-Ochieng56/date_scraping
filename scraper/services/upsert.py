from __future__ import annotations

from typing import Any, Tuple

from django.db import transaction

from leads.models import Lead
from scraper.models import ScrapeTarget
from scraper.services.hashing import sha256_of_obj
from scraper.services.normalize import normalize_phone, parse_date, parse_datetime


def _get_first(item: dict[str, Any], keys: list[str]) -> str:
    for k in keys:
        v = item.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _map_item_to_lead_fields(target: ScrapeTarget, item: dict[str, Any]) -> dict[str, Any]:
    full_name = _get_first(item, ["full_name", "name"])
    email = _get_first(item, ["email", "email_address"])
    phone = _get_first(item, ["phone", "phone_number", "phonenumber"])
    company = _get_first(item, ["company", "organization"])
    position = _get_first(item, ["position", "title", "job_title", "role"])
    website = _get_first(item, ["website", "url", "website_url", "site"])
    
    # Address fields
    address = _get_first(item, ["address", "street", "street_address"])
    city = _get_first(item, ["city", "location_city"])
    state = _get_first(item, ["state", "province", "region", "location_state"])
    zip_code = _get_first(item, ["zip_code", "zip", "postal_code", "postcode"])
    country_code = _get_first(item, ["country_code", "country", "location_country"])
    
    # Translation event specific fields
    default_language = _get_first(item, ["default_language", "language", "lang", "preferred_language"])
    lead_value = item.get("lead_value") or item.get("value")
    if lead_value:
        try:
            lead_value = float(lead_value)
        except (ValueError, TypeError):
            lead_value = None
    else:
        lead_value = None

    event_text = _get_first(item, ["event_text", "date_text", "event_description", "description"])
    event_dt = None
    event_date = None
    if item.get("event_datetime"):
        event_dt = parse_datetime(str(item.get("event_datetime")))
    elif item.get("datetime"):
        event_dt = parse_datetime(str(item.get("datetime")))
    if item.get("event_date"):
        event_date = parse_date(str(item.get("event_date")))
    elif item.get("date"):
        event_date = parse_date(str(item.get("date")))
    if event_dt and not event_date:
        event_date = event_dt.date()

    normalized = normalize_phone(phone, default_region=None) if phone else None
    
    # Use normalized country code if available, otherwise use extracted
    final_country_code = normalized.country_code if normalized else (country_code[:2].upper() if country_code else "")

    return {
        "source_name": target.name,
        "source_url": str(item.get("_page_url") or target.start_url or ""),
        "source_ref": _get_first(item, ["source_ref", "id", "ref", "listing_id"]),
        "full_name": full_name,
        "email": email or None,
        "phone_raw": phone,
        "phone_e164": normalized.e164 if normalized else "",
        "country_code": final_country_code,
        "company": company,
        "position": position,
        "website": website,
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "default_language": default_language,
        "lead_value": lead_value,
        "event_text": event_text,
        "event_datetime": event_dt,
        "event_date": event_date,
    }


@transaction.atomic
def upsert_lead_from_item(target: ScrapeTarget, item: dict[str, Any]) -> Tuple[Lead, bool]:
    """
    Upsert strategy (simple + robust):
      1) match by email (if present)
      2) else match by phone_e164 (if present)
      3) else match by raw_payload_hash (if present)
      4) else create new
    """
    raw_hash = sha256_of_obj(item)
    fields = _map_item_to_lead_fields(target, item)

    qs = Lead.objects.all()
    existing: Lead | None = None

    if fields.get("email"):
        existing = qs.filter(email__iexact=fields["email"]).order_by("-id").first()

    if existing is None and fields.get("phone_e164"):
        existing = qs.filter(phone_e164=fields["phone_e164"]).order_by("-id").first()

    if existing is None and raw_hash:
        existing = qs.filter(raw_payload_hash=raw_hash).order_by("-id").first()

    if existing is None:
        lead = Lead.objects.create(
            **fields,
            raw_payload=item,
            raw_payload_hash=raw_hash,
        )
        return lead, True

    # Update fields cautiously: prefer new non-empty values, don’t erase existing.
    dirty: dict[str, Any] = {}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, str):
            if v.strip() and (getattr(existing, k) or "").strip() != v.strip():
                dirty[k] = v.strip()
        else:
            if v and getattr(existing, k) != v:
                dirty[k] = v

    dirty["raw_payload"] = item
    dirty["raw_payload_hash"] = raw_hash

    for k, v in dirty.items():
        setattr(existing, k, v)
    existing.save(update_fields=list(dirty.keys()) + ["updated_at"])

    return existing, False

