"""
Upsert service for creating/updating Prospects from scraped items.

This module handles the conversion of raw scraped data into Prospect records.
Prospects are pre-contact discovery records with minimal fields (Event Name, Company, Email, Phone, Website).

After contact, Prospects can be converted to Leads via the convert_to_lead() method.
"""

from __future__ import annotations

from typing import Any, Tuple

from django.db import transaction

from leads.models import Prospect
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


def _map_item_to_prospect_fields(target: ScrapeTarget, item: dict[str, Any]) -> dict[str, Any]:
    """Map scraped item to Prospect fields (minimal pre-contact info)."""
    email = _get_first(item, ["email", "email_address"])
    phone = _get_first(item, ["phone", "phone_number", "phonenumber"])
    company = _get_first(item, ["company", "organization"])
    website = _get_first(item, ["website", "url", "website_url", "site"])
    event_name = _get_first(item, ["event_name", "event_text", "date_text", "event_description", "description"])

    normalized = normalize_phone(phone, default_region=None) if phone else None

    return {
        "source_name": target.name,
        "source_url": str(item.get("_page_url") or target.start_url or ""),
        "source_ref": _get_first(item, ["source_ref", "id", "ref", "listing_id"]),
        "email": email or None,
        "phone_raw": phone,
        "phone_e164": normalized.e164 if normalized else "",
        "company": company,
        "website": website,
        "event_name": event_name,
    }


@transaction.atomic
def upsert_prospect_from_item(target: ScrapeTarget, item: dict[str, Any]) -> Tuple[Prospect, bool]:
    """
    Upsert strategy for Prospects (simple + robust):
      1) match by email (if present)
      2) else match by phone_e164 (if present)
      3) else match by raw_payload_hash (if present)
      4) else create new
    
    Returns (Prospect, created) tuple.
    """
    raw_hash = sha256_of_obj(item)
    fields = _map_item_to_prospect_fields(target, item)

    qs = Prospect.objects.all()
    existing: Prospect | None = None

    if fields.get("email"):
        existing = qs.filter(email__iexact=fields["email"]).order_by("-id").first()

    if existing is None and fields.get("phone_e164"):
        existing = qs.filter(phone_e164=fields["phone_e164"]).order_by("-id").first()

    if existing is None and raw_hash:
        existing = qs.filter(raw_payload_hash=raw_hash).order_by("-id").first()

    if existing is None:
        prospect = Prospect.objects.create(
            **fields,
            raw_payload=item,
            raw_payload_hash=raw_hash,
        )
        return prospect, True

    # Update fields cautiously: prefer new non-empty values, don't erase existing.
    # Only update if prospect hasn't been converted or rejected
    if existing.status in ["converted", "rejected"]:
        return existing, False
    
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

