"""Start and query bounded scrape sessions (shared by API views and beat tasks)."""

from __future__ import annotations

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from scraper.models import ScrapeSession, ScrapeSessionStatus
from scraper.tasks import finalize_scrape_session, scrape_session_coordinator_task

User = get_user_model()


class SessionStartError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def scrape_sessions_enabled() -> bool:
    return os.getenv("SCRAPER_SESSION_ENABLED", "1") not in ("0", "false", "False", "")


def max_active_scrape_sessions_per_user() -> int:
    return int(os.getenv("SCRAPER_SESSION_MAX_ACTIVE_PER_USER", "1") or "1")


def min_session_duration_minutes() -> int:
    return int(os.getenv("SCRAPER_SESSION_MIN_DURATION_MINUTES", "15") or "15")


def max_session_duration_minutes() -> int:
    return int(os.getenv("SCRAPER_SESSION_MAX_DURATION_MINUTES", "1440") or "1440")


def user_has_active_scrape_session(user_id: int) -> bool:
    now = timezone.now()
    return (
        ScrapeSession.objects.filter(
            owner_id=user_id,
            status=ScrapeSessionStatus.RUNNING,
            ends_at__gt=now,
        ).count()
        >= max_active_scrape_sessions_per_user()
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


def start_scrape_session_for_user(user, duration_minutes: int, *, notify: bool = True) -> ScrapeSession:
    if not scrape_sessions_enabled():
        raise SessionStartError("Scrape sessions are disabled.", status_code=503)

    duration_minutes = validate_session_duration(duration_minutes)

    if user_has_active_scrape_session(user.id):
        raise SessionStartError("You already have an active scrape session.", status_code=400)

    now = timezone.now()
    ends_at = now + timedelta(minutes=duration_minutes)
    session = ScrapeSession.objects.create(
        owner=user,
        status=ScrapeSessionStatus.RUNNING,
        started_at=now,
        ends_at=ends_at,
        duration_minutes=duration_minutes,
        stats={"targets_enqueued": 0, "cycles_completed": 0},
    )

    coord = scrape_session_coordinator_task.delay(session.id)
    session.coordinator_task_id = coord.id or ""
    session.save(update_fields=["coordinator_task_id"])

    finalize_scrape_session.apply_async(args=[session.id, "deadline"], eta=ends_at)
    if notify:
        from dashboard.utils import notify_scrape_session

        notify_scrape_session(user, session, "started")

    return session
