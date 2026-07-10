"""Shared crawl session helpers for staff and admin API views."""

from __future__ import annotations

from django.utils import timezone

from crawler.models import CrawlRun, CrawlRunStatus, CrawlRunTrigger


def active_crawl_sessions_qs():
    now = timezone.now()
    return (
        CrawlRun.objects.filter(
            status=CrawlRunStatus.RUNNING,
            trigger=CrawlRunTrigger.SESSION,
            ends_at__gt=now,
        )
        .select_related("owner")
        .order_by("-started_at")
    )


def serialize_crawl_session_run(run: CrawlRun, *, include_owner: bool = False) -> dict:
    time_remaining = None
    if run.ends_at and run.status == CrawlRunStatus.RUNNING:
        time_remaining = max(0, int((run.ends_at - timezone.now()).total_seconds()))

    data = {
        "id": run.id,
        "trigger": run.trigger,
        "status": run.status,
        "status_display": run.get_status_display(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "ends_at": run.ends_at.isoformat() if run.ends_at else None,
        "duration_minutes": run.duration_minutes,
        "cycles_completed": run.cycles_completed,
        "last_cycle_at": run.last_cycle_at.isoformat() if run.last_cycle_at else None,
        "time_remaining_seconds": time_remaining,
        "is_session_active": bool(
            run.status == CrawlRunStatus.RUNNING
            and run.trigger == CrawlRunTrigger.SESSION
            and run.ends_at
            and run.ends_at > timezone.now()
        ),
        "task_id": run.task_id,
        "coordinator_task_id": run.coordinator_task_id,
        "error_text": run.error_text,
        "domains_queued": run.domains_queued,
        "prospects_created": run.prospects_created,
        "prospects_updated": run.prospects_updated,
        "owner_id": run.owner_id,
    }
    if include_owner:
        data["owner_username"] = getattr(run.owner, "username", "") if run.owner_id else ""
    return data
