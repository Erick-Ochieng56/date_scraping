from __future__ import annotations

from django.contrib.auth.models import User
from django.utils import timezone

from dashboard.models import ActivityLog, Notification


def log_activity(
    action: str,
    object_type: str,
    object_id: int,
    description: str,
    user: User | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    """Helper function to create activity log entries."""
    return ActivityLog.objects.create(
        user=user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        description=description,
        metadata=metadata or {},
    )


def create_notification(
    user: User,
    title: str,
    message: str,
    notification_type: str = 'info',
    link_url: str = '',
    metadata: dict | None = None,
) -> Notification:
    """Helper function to create user notifications."""
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        link_url=link_url,
        metadata=metadata or {},
    )


def create_notification_for_all_users(
    title: str,
    message: str,
    notification_type: str = 'info',
    link_url: str = '',
    metadata: dict | None = None,
) -> list[Notification]:
    """Create notification for all active users."""
    notifications = []
    for user in User.objects.filter(is_active=True):
        notifications.append(
            Notification.objects.create(
                user=user,
                type=notification_type,
                title=title,
                message=message,
                link_url=link_url,
                metadata=metadata or {},
            )
        )
    return notifications


def notify_scrape_run(
    owner_id: int | None,
    *,
    title: str,
    message: str,
    notification_type: str = "info",
    link_url: str = "",
    metadata: dict | None = None,
) -> None:
    """Notify the run owner when known; otherwise broadcast to all active users."""
    if owner_id:
        user = User.objects.filter(id=owner_id).first()
        if user:
            create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                link_url=link_url,
                metadata=metadata,
            )
            return
    create_notification_for_all_users(
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
        metadata=metadata,
    )


def notify_crawl_session(user: User, run, event: str) -> None:
    """In-app notification for crawl session lifecycle events."""
    link_url = f"/crawler/runs/{run.id}"
    duration = int(run.duration_minutes or 0)
    domains = int(run.domains_queued or 0)
    prospects = int(run.prospects_created or 0)
    cycles = int(run.cycles_completed or 0)

    if event == "started":
        if duration >= 60 and duration % 60 == 0:
            dur_label = f"{duration // 60}h"
        else:
            dur_label = f"{duration}m"
        ends = ""
        if run.ends_at:
            ends = f" Ends {run.ends_at.strftime('%b %d, %H:%M %Z')}."
        create_notification(
            user=user,
            title=f"Crawl session started ({dur_label})",
            message=f"Session #{run.id} is running.{ends}",
            notification_type="info",
            link_url=link_url,
            metadata={"run_id": run.id, "event": event},
        )
    elif event in ("completed", "deadline"):
        create_notification(
            user=user,
            title="Crawl session finished",
            message=(
                f"{cycles} cycle(s), {domains} domains queued, "
                f"{prospects} prospect(s) created."
            ),
            notification_type="success",
            link_url=link_url,
            metadata={"run_id": run.id, "event": event},
        )
    elif event == "cancelled":
        create_notification(
            user=user,
            title="Crawl session stopped early",
            message=f"Session #{run.id} was cancelled.",
            notification_type="warning",
            link_url=link_url,
            metadata={"run_id": run.id, "event": event},
        )
    elif event == "failed":
        create_notification(
            user=user,
            title="Crawl session failed",
            message=(run.error_text or "An error stopped the session.")[:500],
            notification_type="error",
            link_url=link_url,
            metadata={"run_id": run.id, "event": event},
        )
    elif event == "progress":
        elapsed_min = 0
        if run.started_at:
            elapsed_min = int((timezone.now() - run.started_at).total_seconds() // 60)
        elapsed_label = f"{elapsed_min // 60}h {elapsed_min % 60}m" if elapsed_min >= 60 else f"{elapsed_min}m"
        create_notification(
            user=user,
            title="Crawl session update",
            message=(
                f"{elapsed_label} elapsed · {cycles} cycle(s) · "
                f"{domains} domains queued · {prospects} prospect(s) created."
            ),
            notification_type="info",
            link_url=link_url,
            metadata={"run_id": run.id, "event": event},
        )


def notify_scrape_session(user: User, session, event: str) -> None:
    """In-app notification for scrape session lifecycle events."""
    link_url = "/targets"
    duration = int(session.duration_minutes or 0)
    stats = dict(session.stats or {})
    targets_enqueued = int(stats.get("targets_enqueued", 0))
    cycles = int(session.cycles_completed or 0)

    if event == "started":
        if duration >= 60 and duration % 60 == 0:
            dur_label = f"{duration // 60}h"
        else:
            dur_label = f"{duration}m"
        ends = ""
        if session.ends_at:
            ends = f" Ends {session.ends_at.strftime('%b %d, %H:%M %Z')}."
        create_notification(
            user=user,
            title=f"Scrape session started ({dur_label})",
            message=f"Session #{session.id} is running.{ends}",
            notification_type="info",
            link_url=link_url,
            metadata={"session_id": session.id, "event": event},
        )
    elif event in ("completed", "deadline"):
        create_notification(
            user=user,
            title="Scrape session finished",
            message=f"{cycles} cycle(s), {targets_enqueued} target scrape(s) enqueued.",
            notification_type="success",
            link_url=link_url,
            metadata={"session_id": session.id, "event": event},
        )
    elif event == "cancelled":
        create_notification(
            user=user,
            title="Scrape session stopped early",
            message=f"Session #{session.id} was cancelled.",
            notification_type="warning",
            link_url=link_url,
            metadata={"session_id": session.id, "event": event},
        )
    elif event == "failed":
        create_notification(
            user=user,
            title="Scrape session failed",
            message=(session.error_text or "An error stopped the session.")[:500],
            notification_type="error",
            link_url=link_url,
            metadata={"session_id": session.id, "event": event},
        )
    elif event == "progress":
        elapsed_min = 0
        if session.started_at:
            elapsed_min = int((timezone.now() - session.started_at).total_seconds() // 60)
        elapsed_label = f"{elapsed_min // 60}h {elapsed_min % 60}m" if elapsed_min >= 60 else f"{elapsed_min}m"
        create_notification(
            user=user,
            title="Scrape session update",
            message=(
                f"{elapsed_label} elapsed · {cycles} cycle(s) · "
                f"{targets_enqueued} target scrape(s) enqueued."
            ),
            notification_type="info",
            link_url=link_url,
            metadata={"session_id": session.id, "event": event},
        )

