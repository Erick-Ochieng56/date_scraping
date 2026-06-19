from __future__ import annotations

from crawler.models import AISearchResult
from crawler.utils import compute_payload_hash, normalize_domain_url
from leads.models import Prospect, ProspectStatus


def _website_from_result(result: AISearchResult) -> str:
    raw = result.raw_data if isinstance(result.raw_data, dict) else {}
    src = (raw.get("source_url") or raw.get("landing_url") or "").strip()
    if src:
        return normalize_domain_url(src) or src
    dom = (result.domain or "").strip().lower().removeprefix("www.")
    if not dom:
        return ""
    if "://" in dom:
        return normalize_domain_url(dom) or dom
    return f"https://{dom}"


def _company_name(result: AISearchResult) -> str:
    name = (result.org_name or "").strip()
    if name:
        return name[:255]
    dom = (result.domain or "").strip().lower().removeprefix("www.")
    if dom:
        return dom.split(".")[0].replace("-", " ").title()[:255]
    return "Unknown organization"


def promote_ai_search_result_to_prospect(
    result: AISearchResult,
    *,
    owner_id: int | None,
) -> tuple[Prospect, bool]:
    """
    Create (or return existing) Prospect from a verified AISearchResult.
    """
    raw = result.raw_data if isinstance(result.raw_data, dict) else {}
    existing_id = raw.get("promoted_prospect_id")
    if existing_id:
        try:
            return Prospect.objects.get(pk=int(existing_id)), False
        except (Prospect.DoesNotExist, TypeError, ValueError):
            pass

    company = _company_name(result)
    website = _website_from_result(result)
    email = (result.contact_email or "").strip() or None
    source_url = website
    raw_src = (raw.get("source_url") or "").strip()
    if raw_src:
        source_url = raw_src

    payload = {
        "source": "ai_search",
        "ai_search_result_id": result.id,
        "job_id": result.job_id,
        "domain": result.domain,
        "org_name": company,
        "org_type": result.org_type,
        "why_needs_translation": result.why_needs_translation,
        "international_signals": result.international_signals or [],
        "contact_email": email or "",
        "translation_need_score": raw.get("translation_need_score"),
        "evidence_snippet": raw.get("evidence_snippet", ""),
    }
    payload_hash = compute_payload_hash(payload)

    qs = Prospect.objects.all()
    if owner_id:
        qs = qs.filter(owner_id=owner_id)
    existing = None
    if email:
        existing = qs.filter(email=email).first()
    if not existing and website:
        existing = qs.filter(website=website).first()
    if not existing:
        existing = qs.filter(raw_payload_hash=payload_hash).first()

    if existing:
        raw["promoted_prospect_id"] = existing.id
        result.raw_data = raw
        result.save(update_fields=["raw_data"])
        return existing, False

    notes_parts = [result.why_needs_translation or ""]
    evidence = (raw.get("evidence_snippet") or "").strip()
    if evidence and evidence not in notes_parts[0]:
        notes_parts.append(evidence)
    score = raw.get("translation_need_score")
    if score is not None:
        notes_parts.append(f"AI score: {score}")

    prospect = Prospect.objects.create(
        owner_id=owner_id,
        source_name="ai_search",
        source_url=source_url[:2000] if source_url else "",
        company=company,
        email=email,
        website=website,
        event_name=(result.why_needs_translation or "")[:255],
        raw_payload=payload,
        raw_payload_hash=payload_hash,
        status=ProspectStatus.NEW,
        notes="\n".join(p for p in notes_parts if p)[:2000],
    )
    raw["promoted_prospect_id"] = prospect.id
    result.raw_data = raw
    result.save(update_fields=["raw_data"])
    return prospect, True
