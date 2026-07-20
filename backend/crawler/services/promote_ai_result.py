from __future__ import annotations

from django.db import transaction

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

    Race guard: the whole check-then-create sequence runs under a row lock on
    this AISearchResult (select_for_update), so two near-simultaneous promote
    calls for the *same* result — a double-click, or the owner and an admin
    both promoting it around the same time — serialize instead of both passing
    the "not yet promoted" check and creating two Prospect rows. This does not
    (and can't cheaply) guard against two *different* results that happen to
    share an email/website racing each other; that would need a DB-level
    unique constraint on Prospect.email/website, which isn't a safe default
    here (see promote_ai_result's email-based-dedup caveat: a shared inbox
    across genuinely distinct organizations is a real, not hypothetical, case
    on procurement portals).
    """
    with transaction.atomic():
        locked_result = AISearchResult.objects.select_for_update().get(pk=result.pk)

        raw = locked_result.raw_data if isinstance(locked_result.raw_data, dict) else {}
        existing_id = raw.get("promoted_prospect_id")
        if existing_id:
            try:
                return Prospect.objects.get(pk=int(existing_id)), False
            except (Prospect.DoesNotExist, TypeError, ValueError):
                pass

        company = _company_name(locked_result)
        website = _website_from_result(locked_result)
        email = (locked_result.contact_email or "").strip() or None
        source_url = website
        raw_src = (raw.get("source_url") or "").strip()
        if raw_src:
            source_url = raw_src

        payload = {
            "source": "ai_search",
            "ai_search_result_id": locked_result.id,
            "job_id": locked_result.job_id,
            "domain": locked_result.domain,
            "org_name": company,
            "org_type": locked_result.org_type,
            "why_needs_translation": locked_result.why_needs_translation,
            "international_signals": locked_result.international_signals or [],
            "contact_email": email or "",
            "translation_need_score": raw.get("translation_need_score"),
            "evidence_snippet": raw.get("evidence_snippet", ""),
        }
        payload_hash = compute_payload_hash(payload)

        # Exact owner match (including owner_id=None -> IS NULL) — not "if owner_id"
        # truthy-only, which would otherwise search/match across every owner's
        # Prospects whenever owner_id is None instead of scoping to the unowned pool.
        qs = Prospect.objects.filter(owner_id=owner_id)
        existing = None
        if email:
            existing = qs.filter(email=email).first()
        if not existing and website:
            existing = qs.filter(website=website).first()
        if not existing:
            existing = qs.filter(raw_payload_hash=payload_hash).first()

        if existing:
            raw["promoted_prospect_id"] = existing.id
            locked_result.raw_data = raw
            locked_result.save(update_fields=["raw_data"])
            return existing, False

        notes_parts = [locked_result.why_needs_translation or ""]
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
            event_name=(locked_result.why_needs_translation or "")[:255],
            raw_payload=payload,
            raw_payload_hash=payload_hash,
            status=ProspectStatus.NEW,
            notes="\n".join(p for p in notes_parts if p)[:2000],
        )
        raw["promoted_prospect_id"] = prospect.id
        locked_result.raw_data = raw
        locked_result.save(update_fields=["raw_data"])
        return prospect, True
