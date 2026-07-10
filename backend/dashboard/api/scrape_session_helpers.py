"""Shared scrape session helpers for staff and admin API views."""

from django.utils import timezone

from scraper.models import ScrapeSession, ScrapeSessionStatus


def active_scrape_sessions_qs():
    now = timezone.now()
    return (
        ScrapeSession.objects.filter(
            status=ScrapeSessionStatus.RUNNING,
            ends_at__gt=now,
        )
        .select_related("owner")
        .order_by("-started_at")
    )


def serialize_scrape_session(session: ScrapeSession, *, include_owner: bool = False) -> dict:
    from dashboard.api.serializers import ScrapeSessionSerializer

    data = dict(ScrapeSessionSerializer(session).data)
    if include_owner and session.owner_id:
        data["owner_username"] = session.owner.username if session.owner else ""
    return data
