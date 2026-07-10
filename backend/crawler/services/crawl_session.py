"""Start and query bounded crawl sessions (shared by API views and beat tasks)."""

from __future__ import annotations

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from crawler.models import CrawlRun, CrawlRunStatus, CrawlRunTrigger
from crawler.tasks import _get_session_config, crawl_session_coordinator_task, finalize_crawl_session
from dashboard.utils import notify_crawl_session

User = get_user_model()


class SessionStartError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def crawl_sessions_enabled() -> bool:
    return os.getenv("CRAWLER_SESSION_ENABLED", "1") not in ("0", "false", "False", "")


def max_active_crawl_sessions_per_user() -> int:
    return int(os.getenv("CRAWLER_SESSION_MAX_ACTIVE_PER_USER", "1") or "1")


def default_schedule_session_minutes() -> int:
    return int(os.getenv("CRAWLER_SCHEDULE_DEFAULT_SESSION_MINUTES", "360") or "360")


def min_session_duration_minutes() -> int:
    return int(os.getenv("CRAWLER_SESSION_MIN_DURATION_MINUTES", "15") or "15")


def max_session_duration_minutes() -> int:
    return int(os.getenv("CRAWLER_SESSION_MAX_DURATION_MINUTES", "1440") or "1440")


def user_has_active_crawl_session(user_id: int) -> bool:
    now = timezone.now()
    return (
        CrawlRun.objects.filter(
            owner_id=user_id,
            status=CrawlRunStatus.RUNNING,
            trigger=CrawlRunTrigger.SESSION,
            ends_at__gt=now,
        ).count()
        >= max_active_crawl_sessions_per_user()
    )


def validate_session_duration(duration_minutes: int) -> int:
    duration = int(duration_minutes)
    min_d = min_session_duration_minutes()
    max_d = max_session_duration_minutes()
    if duration < min_d or duration > max_d:
        raise SessionStartError(
            f"duration_minutes must be between {min_d} and {max_d}.",
            status_code=400,
        )
    return duration


def start_crawl_session_for_user(user, duration_minutes: int, *, notify: bool = True) -> CrawlRun:
    if not crawl_sessions_enabled():
        raise SessionStartError("Crawl sessions are disabled.", status_code=503)

    duration_minutes = validate_session_duration(duration_minutes)

    if user_has_active_crawl_session(user.id):
        raise SessionStartError("You already have an active crawl session.", status_code=400)

    now = timezone.now()
    ends_at = now + timedelta(minutes=duration_minutes)
    run = CrawlRun.objects.create(
        owner=user,
        trigger=CrawlRunTrigger.SESSION,
        status=CrawlRunStatus.RUNNING,
        started_at=now,
        ends_at=ends_at,
        duration_minutes=duration_minutes,
        session_mode=True,
        config=_get_session_config(),
        stats={
            "domains_discovered": 0,
            "domains_crawled": 0,
            "domains_failed": 0,
            "pages_crawled": 0,
            "prospects_created": 0,
            "prospects_updated": 0,
            "high_score_leads": 0,
            "medium_score_leads": 0,
            "services_detected": {},
        },
    )

    coord = crawl_session_coordinator_task.delay(run.id)
    run.coordinator_task_id = coord.id or ""
    run.save(update_fields=["coordinator_task_id"])

    finalize_crawl_session.apply_async(args=[run.id, "deadline"], eta=ends_at)
    if notify:
        notify_crawl_session(user, run, "started")

    return run
