from __future__ import annotations

import logging
from typing import Any

from django.db import models, transaction

from crawler.models import WebsiteProfile
from crawler.scoring import get_score_label
from crawler.utils import compute_payload_hash, normalize_domain_url

logger = logging.getLogger(__name__)


def build_raw_payload(profile: WebsiteProfile, score: int) -> dict[str, Any]:
    """Build canonical raw payload for Prospect.raw_payload."""
    return {
        "domain": profile.domain.domain,
        "org_name": profile.org_name,
        "org_type": profile.org_type,
        "detected_org_types": profile.detected_org_types,
        "detected_services": profile.detected_services,
        "languages_detected": profile.languages_detected,
        "countries_detected": profile.countries_detected,
        "international_signals": profile.international_signals,
        "event_names": profile.event_names,
        "contact_emails": profile.contact_emails,
        "contact_phones": profile.contact_phones,
        "translation_need_score": score,
        "score_label": get_score_label(score),
        "pages_crawled": profile.pages_crawled,
        "analyzed_at": profile.analyzed_at.isoformat() if profile.analyzed_at else None,
    }


def create_or_update_prospect(profile: WebsiteProfile, score: int):
    """
    Create or update a Prospect from a WebsiteProfile.

    Deduplication order:
      1. raw_payload_hash (exact duplicate)
      2. email (same contact)
      3. website URL (same org)
    """
    from leads.models import Prospect, ProspectStatus

    payload = build_raw_payload(profile, score)
    payload_hash = compute_payload_hash(payload)

    email = (profile.contact_emails[0] if profile.contact_emails else None) or None
    website = normalize_domain_url(profile.domain.domain)
    phone_e164 = (profile.contact_phones[0] if profile.contact_phones else "") or ""

    with transaction.atomic():
        existing = Prospect.objects.filter(
            models.Q(raw_payload_hash=payload_hash)
            | (models.Q(email=email) if email else models.Q(pk__in=[]))
            | (models.Q(website=website) if website else models.Q(pk__in=[]))
        ).first()

        if existing:
            existing.source_name = "web_crawler"
            existing.source_url = website
            existing.company = profile.org_name or website
            if email:
                existing.email = email
            if phone_e164:
                existing.phone_e164 = phone_e164
                existing.phone_raw = existing.phone_raw or phone_e164
            existing.website = website
            existing.event_name = (profile.event_names[0] if profile.event_names else "") or ""
            existing.raw_payload = payload
            existing.raw_payload_hash = payload_hash
            existing.save()
            return existing, False

        prospect = Prospect.objects.create(
            source_name="web_crawler",
            source_url=website,
            company=profile.org_name or website,
            email=email,
            phone_raw=phone_e164,
            phone_e164=phone_e164,
            website=website,
            event_name=(profile.event_names[0] if profile.event_names else "") or "",
            raw_payload=payload,
            raw_payload_hash=payload_hash,
            status=ProspectStatus.NEW,
        )
        return prospect, True

