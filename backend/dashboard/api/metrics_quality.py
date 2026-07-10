from __future__ import annotations

from collections import Counter

from django.db.models import Count, Q

from dashboard.api.prospect_quality import prospect_translation_need_score
from leads.models import LeadStatus, ProspectStatus


def _categorize_drop_reason(reason: str) -> str:
    r = (reason or "").lower()
    if any(k in r for k in ("competitor", "lsp", "translation agency", "language service provider")):
        return "competitor"
    if any(k in r for k in ("geo", "east africa", "region", "country")):
        return "geo"
    if any(k in r for k in ("directory", "aggregator", "listing site")):
        return "directory"
    if any(k in r for k in ("stale", "archived", "past year")):
        return "stale"
    if any(k in r for k in ("active buyer", "buyer")):
        return "buyer_gate"
    return "other"


def _normalize_drop_summary_key(key: str) -> str:
    return _categorize_drop_reason(key.replace("_", " "))


def build_quality_metrics(*, prospects_qs, leads_qs, event_prospects_qs, crawl_domain_qs, since) -> dict:
    tiers = {"high": 0, "medium": 0, "low": 0, "unscored": 0}
    for payload in prospects_qs.values_list("raw_payload", flat=True):
        raw = payload if isinstance(payload, dict) else {}
        val = raw.get("translation_need_score")
        try:
            score = int(val) if val is not None else None
        except (TypeError, ValueError):
            score = None
        if score is None:
            tiers["unscored"] += 1
        elif score >= 61:
            tiers["high"] += 1
        elif score >= 31:
            tiers["medium"] += 1
        else:
            tiers["low"] += 1

    high_score_new = 0
    for p in prospects_qs.filter(status=ProspectStatus.NEW).only("raw_payload"):
        score = prospect_translation_need_score(p)
        if score is not None and score >= 60:
            high_score_new += 1

    enrichment_backlog = (
        prospects_qs.filter(status=ProspectStatus.NEW)
        .exclude(source_url="")
        .filter(Q(email__isnull=True) | Q(email=""))
        .count()
    )

    source_rows = (
        prospects_qs.exclude(source_name="")
        .values("source_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )

    return {
        "prospect_score_tiers": tiers,
        "prospects_high_score_new": high_score_new,
        "event_prospects_new": event_prospects_qs.filter(status="new").count(),
        "enrichment_backlog": enrichment_backlog,
        "leads_ready_to_sync": leads_qs.filter(status=LeadStatus.INTERESTED).count(),
        "crawl_competitors_7d": crawl_domain_qs.filter(is_competitor=True, processed_at__gte=since).count(),
        "prospects_by_source": list(source_rows),
    }


def build_discovery_drop_metrics(*, ai_jobs_qs, crawl_domain_qs, since) -> dict:
    category_counts: Counter[str] = Counter()
    reason_samples: dict[str, list[str]] = {
        "competitor": [],
        "geo": [],
        "directory": [],
        "stale": [],
        "buyer_gate": [],
        "other": [],
    }

    for log in ai_jobs_qs.values_list("qualification_log", flat=True):
        if not isinstance(log, dict):
            continue
        summary = log.get("drop_summary") or {}
        if isinstance(summary, dict):
            for key, count in summary.items():
                cat = _normalize_drop_summary_key(str(key))
                category_counts[cat] += int(count or 0)
        for drop in log.get("drops") or []:
            if not isinstance(drop, dict):
                continue
            reason = str(drop.get("reason") or "")
            cat = _categorize_drop_reason(reason)
            if len(reason_samples[cat]) < 3 and reason:
                reason_samples[cat].append(reason[:200])

    competitor_crawl = crawl_domain_qs.filter(is_competitor=True, processed_at__gte=since).count()
    category_counts["competitor"] += competitor_crawl

    recent_jobs = ai_jobs_qs.count()
    total_dropped = sum(category_counts.values())

    return {
        "period_days": 7,
        "ai_search_jobs_analyzed": recent_jobs,
        "total_drops_estimated": total_dropped,
        "by_category": dict(category_counts),
        "sample_reasons": reason_samples,
    }
