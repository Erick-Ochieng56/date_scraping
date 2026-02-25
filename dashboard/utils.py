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

