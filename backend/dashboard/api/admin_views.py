from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from dashboard.api.decorators import dashboard_api_view
from dashboard.api.permissions import IsDashboardAdminUser
from dashboard.models import ActivityLog
from dashboard.api.serializers import AISearchJobSerializer, AISearchResultSerializer, CrawlScheduleSerializer
from dashboard.api.crawl_session_helpers import active_crawl_sessions_qs, serialize_crawl_session_run
from dashboard.api.scrape_session_helpers import active_scrape_sessions_qs, serialize_scrape_session
from dashboard.permissions import scraper_group_name
from dashboard.utils import log_activity
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.tasks import scrape_target
from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSchedule,
    CrawlSource,
    DiscoveredDomain,
)
from crawler.discovery import _get_serper_api_key
from crawler.services.promote_ai_result import promote_ai_search_result_to_prospect
from crawler.tasks import crawl_domain_task, run_ai_search_job
from leads.models import Lead, Prospect
from celery import current_app
from django.utils import timezone

User = get_user_model()


def _parse_positive_int(value, *, field: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        parsed = default
    else:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValidationError({field: f"{field} must be an integer."}) from exc
    if parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _parse_optional_bool(value, *, field: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValidationError({field: f"{field} must be a boolean value."})


def _pagination(request: Request, rows: list[dict]):
    page = _parse_positive_int(request.query_params.get("page"), field="page", default=1, minimum=1)
    page_size = _parse_positive_int(
        request.query_params.get("page_size"),
        field="page_size",
        default=25,
        minimum=1,
        maximum=100,
    )
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": rows[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": end < total,
    }


def _serialize_user(user, scraper_group: Group) -> dict:
    role = "admin" if user.is_staff else ("staff" if user.groups.filter(id=scraper_group.id).exists() else "none")
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email or "",
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "role": role,
        "groups": list(user.groups.values_list("name", flat=True)),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if getattr(user, "date_joined", None) else None,
    }


def _serialize_activity_log(entry: ActivityLog) -> dict:
    return {
        "id": entry.id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "user_id": entry.user_id,
        "username": entry.user.get_username() if entry.user_id else None,
        "action": entry.action,
        "action_display": entry.get_action_display(),
        "object_type": entry.object_type,
        "object_id": entry.object_id,
        "description": entry.description,
        "metadata": entry.metadata or {},
    }


def _env_truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _setting_or_env_str(setting_name: str, env_name: str, default: str = "") -> str:
    raw = getattr(settings, setting_name, None)
    if raw is not None:
        return str(raw).strip()
    return (os.getenv(env_name, default) or default).strip()


def _setting_or_env_bool(setting_name: str, env_name: str, default: str = "0") -> bool:
    raw = getattr(settings, setting_name, None)
    if isinstance(raw, bool):
        return raw
    if raw is not None:
        return str(raw).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return _env_truthy(env_name, default)


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def activity_list(request: Request) -> Response:
    qs = ActivityLog.objects.select_related("user").all().order_by("-created_at")
    action = (request.query_params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)
    object_type = (request.query_params.get("object_type") or "").strip()
    if object_type:
        qs = qs.filter(object_type=object_type)
    user_id = (request.query_params.get("user_id") or "").strip()
    if user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(description__icontains=search)

    page = _parse_positive_int(request.query_params.get("page"), field="page", default=1, minimum=1)
    page_size = _parse_positive_int(
        request.query_params.get("page_size"),
        field="page_size",
        default=25,
        minimum=1,
        maximum=100,
    )
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    items = [_serialize_activity_log(e) for e in qs[start:end]]
    return Response(
        {
            "success": True,
            "data": {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": end < total,
            },
            "filters": {
                "actions": [{"value": value, "label": label} for value, label in ActivityLog.ACTION_CHOICES],
            },
        }
    )


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def settings_status(request: Request) -> Response:
    gemini_key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
    gsheets_enabled = _setting_or_env_bool("GSHEETS_ENABLED", "GSHEETS_ENABLED", "1")
    gsheets_creds = bool(_setting_or_env_str("GSHEETS_CREDENTIALS_JSON", "GSHEETS_CREDENTIALS_JSON")) or bool(
        _setting_or_env_str("GSHEETS_CREDENTIALS_FILE", "GSHEETS_CREDENTIALS_FILE")
    )
    gsheets_sheet = bool(_setting_or_env_str("GSHEETS_SPREADSHEET_ID", "GSHEETS_SPREADSHEET_ID"))
    perfex_enabled = _setting_or_env_bool("PERFEX_SYNC_ENABLED", "PERFEX_SYNC_ENABLED", "0")
    perfex_base = bool(_setting_or_env_str("PERFEX_BASE_URL", "PERFEX_BASE_URL"))
    perfex_token = bool(_setting_or_env_str("PERFEX_API_TOKEN", "PERFEX_API_TOKEN"))

    crawler_min_score = int(os.getenv("CRAWLER_MIN_SCORE_THRESHOLD", "40") or "40")
    ai_search_min_score = int(getattr(settings, "AI_SEARCH_MIN_SCORE", 80) or 80)

    integrations = [
        {
            "id": "gemini",
            "label": "Google Gemini (AI search & enrichment)",
            "enabled": True,
            "configured": bool(gemini_key),
            "status": "ready" if gemini_key else "missing_api_key",
            "hint": "Set GEMINI_API_KEY in server environment.",
        },
        {
            "id": "gsheets",
            "label": "Google Sheets sync",
            "enabled": gsheets_enabled,
            "configured": gsheets_creds and gsheets_sheet,
            "status": (
                "disabled"
                if not gsheets_enabled
                else ("ready" if gsheets_creds and gsheets_sheet else "incomplete")
            ),
            "hint": "Set GSHEETS_ENABLED, credentials (JSON or file), and GSHEETS_SPREADSHEET_ID.",
        },
        {
            "id": "perfex",
            "label": "Perfex CRM sync",
            "enabled": perfex_enabled,
            "configured": perfex_base and perfex_token,
            "status": (
                "disabled"
                if not perfex_enabled
                else ("ready" if perfex_base and perfex_token else "incomplete")
            ),
            "hint": "Set PERFEX_SYNC_ENABLED=1, PERFEX_BASE_URL, and PERFEX_API_TOKEN.",
        },
    ]
    return Response(
        {
            "success": True,
            "data": {
                "environment": getattr(settings, "ENVIRONMENT", "unknown"),
                "debug": settings.DEBUG,
                "integrations": integrations,
                "thresholds": [
                    {
                        "id": "crawler_min_score",
                        "label": "Crawler min prospect score",
                        "value": crawler_min_score,
                        "env_var": "CRAWLER_MIN_SCORE_THRESHOLD",
                        "description": "Minimum website score to auto-create a prospect during crawl.",
                    },
                    {
                        "id": "ai_search_min_score",
                        "label": "AI search min save score",
                        "value": ai_search_min_score,
                        "env_var": "AI_SEARCH_MIN_SCORE",
                        "description": "Minimum score for AI search results to be saved or promoted.",
                    },
                    {
                        "id": "crawler_session_enabled",
                        "label": "Crawl sessions enabled",
                        "value": 1 if os.getenv("CRAWLER_SESSION_ENABLED", "1") not in ("0", "false", "False", "") else 0,
                        "env_var": "CRAWLER_SESSION_ENABLED",
                        "description": "When 0, staff cannot start bounded crawl sessions.",
                    },
                    {
                        "id": "crawler_session_max_domains_per_cycle",
                        "label": "Session domains per cycle",
                        "value": int(os.getenv("CRAWLER_SESSION_MAX_DOMAINS_PER_CYCLE", "50") or "50"),
                        "env_var": "CRAWLER_SESSION_MAX_DOMAINS_PER_CYCLE",
                        "description": "Max domains enqueued per coordinator cycle during a session.",
                    },
                    {
                        "id": "crawler_session_cycle_interval",
                        "label": "Session cycle interval (seconds)",
                        "value": int(os.getenv("CRAWLER_SESSION_CYCLE_INTERVAL_SECONDS", "600") or "600"),
                        "env_var": "CRAWLER_SESSION_CYCLE_INTERVAL_SECONDS",
                        "description": "Seconds between discovery cycles inside an active session.",
                    },
                    {
                        "id": "crawler_session_max_active",
                        "label": "Max active sessions per user",
                        "value": int(os.getenv("CRAWLER_SESSION_MAX_ACTIVE_PER_USER", "1") or "1"),
                        "env_var": "CRAWLER_SESSION_MAX_ACTIVE_PER_USER",
                        "description": "Parallel crawl sessions allowed per staff user.",
                    },
                    {
                        "id": "crawler_session_progress_notify",
                        "label": "Session progress notify interval (minutes)",
                        "value": int(os.getenv("CRAWLER_SESSION_PROGRESS_NOTIFY_MINUTES", "120") or "120"),
                        "env_var": "CRAWLER_SESSION_PROGRESS_NOTIFY_MINUTES",
                        "description": "In-app progress summaries for sessions ≥6h (0 disables).",
                    },
                    {
                        "id": "scraper_session_enabled",
                        "label": "Scrape sessions enabled",
                        "value": 1 if os.getenv("SCRAPER_SESSION_ENABLED", "1") not in ("0", "false", "False", "") else 0,
                        "env_var": "SCRAPER_SESSION_ENABLED",
                        "description": "When 0, staff cannot start bounded scrape sessions.",
                    },
                    {
                        "id": "scraper_session_cycle_interval",
                        "label": "Scrape session cycle interval (seconds)",
                        "value": int(os.getenv("SCRAPER_SESSION_CYCLE_INTERVAL_SECONDS", "300") or "300"),
                        "env_var": "SCRAPER_SESSION_CYCLE_INTERVAL_SECONDS",
                        "description": "Seconds between enqueue cycles inside an active scrape session.",
                    },
                    {
                        "id": "scraper_session_max_active",
                        "label": "Max active scrape sessions per user",
                        "value": int(os.getenv("SCRAPER_SESSION_MAX_ACTIVE_PER_USER", "1") or "1"),
                        "env_var": "SCRAPER_SESSION_MAX_ACTIVE_PER_USER",
                        "description": "Parallel scrape sessions allowed per staff user.",
                    },
                ],
            },
        }
    )


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def users_list(request: Request) -> Response:
    gname = scraper_group_name()
    scraper_group, _ = Group.objects.get_or_create(name=gname)
    qs = User.objects.all().order_by("username")
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(username__icontains=search)

    rows = [_serialize_user(u, scraper_group) for u in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def users_create_staff(request: Request) -> Response:
    username = (request.data.get("username") or "").strip()
    password = (request.data.get("password") or "").strip()
    email = (request.data.get("email") or "").strip()

    if not username:
        return Response({"success": False, "error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not password:
        return Response({"success": False, "error": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({"success": False, "error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

    gname = scraper_group_name()
    scraper_group, _ = Group.objects.get_or_create(name=gname)

    user = User.objects.create_user(username=username, email=email, password=password)
    user.is_staff = False
    user.is_superuser = False
    user.is_active = True
    user.save(update_fields=["is_staff", "is_superuser", "is_active"])
    user.groups.add(scraper_group)
    log_activity(
        action="user_created",
        object_type="user",
        object_id=user.id,
        description=f"Created staff user {user.get_username()}",
        user=request.user,
        metadata={"role": "staff"},
    )

    return Response({"success": True, "data": _serialize_user(user, scraper_group)}, status=status.HTTP_201_CREATED)


@dashboard_api_view(["PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def users_update(request: Request, user_id: int) -> Response:
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"success": False, "error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    before = {
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }

    gname = scraper_group_name()
    scraper_group, _ = Group.objects.get_or_create(name=gname)

    role = request.data.get("role")
    is_active = _parse_optional_bool(request.data.get("is_active"), field="is_active")

    if is_active is not None:
        if user.id == request.user.id and is_active is False:
            return Response(
                {"success": False, "error": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = is_active

    if role is not None:
        if role not in {"admin", "staff"}:
            return Response({"success": False, "error": "role must be 'admin' or 'staff'."}, status=status.HTTP_400_BAD_REQUEST)
        if role == "admin":
            if not request.user.is_superuser:
                return Response(
                    {"success": False, "error": "Only superadmins can grant admin role."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            user.is_staff = True
            user.groups.remove(scraper_group)
        else:
            if user.id == request.user.id and user.is_superuser:
                return Response(
                    {"success": False, "error": "Superadmin cannot demote self to staff."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.is_staff = False
            user.is_superuser = False
            user.groups.add(scraper_group)

    user.save()
    log_activity(
        action="user_updated",
        object_type="user",
        object_id=user.id,
        description=f"Updated user {user.get_username()}",
        user=request.user,
        metadata={"before": before, "after": {"is_active": user.is_active, "is_staff": user.is_staff, "is_superuser": user.is_superuser}},
    )
    return Response({"success": True, "data": _serialize_user(user, scraper_group)})


_OWNERSHIP_MODELS = {
    "scrape_targets": (ScrapeTarget, "scrape_target"),
    "scrape_runs": (ScrapeRun, "scrape_run"),
    "crawl_runs": (CrawlRun, "crawl_run"),
    "crawl_sources": (CrawlSource, "crawl_source"),
    "crawl_domains": (DiscoveredDomain, "crawl_domain"),
    "prospects": (Prospect, "prospect"),
    "leads": (Lead, "lead"),
}


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def ownership_transfer(request: Request) -> Response:
    object_type = (request.data.get("object_type") or "").strip()
    from_user_id = request.data.get("from_user_id")
    to_user_id = request.data.get("to_user_id")
    transfer_all = bool(request.data.get("transfer_all"))
    object_ids = request.data.get("object_ids") or []

    if object_type not in _OWNERSHIP_MODELS:
        return Response({"success": False, "error": "Invalid object_type."}, status=status.HTTP_400_BAD_REQUEST)
    if not from_user_id or not to_user_id:
        return Response({"success": False, "error": "from_user_id and to_user_id are required."}, status=status.HTTP_400_BAD_REQUEST)
    if int(from_user_id) == int(to_user_id):
        return Response({"success": False, "error": "from_user_id and to_user_id must be different."}, status=status.HTTP_400_BAD_REQUEST)
    if not User.objects.filter(id=from_user_id).exists() or not User.objects.filter(id=to_user_id).exists():
        return Response({"success": False, "error": "Source or destination user not found."}, status=status.HTTP_404_NOT_FOUND)

    model, object_label = _OWNERSHIP_MODELS[object_type]
    qs = model.objects.filter(owner_id=from_user_id)
    if not transfer_all:
        if not object_ids:
            return Response(
                {"success": False, "error": "object_ids required when transfer_all=false."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(id__in=object_ids)

    with transaction.atomic():
        ids = list(qs.values_list("id", flat=True))
        count = qs.update(owner_id=to_user_id)

    log_activity(
        action="ownership_transferred",
        object_type=object_label,
        object_id=ids[0] if ids else 0,
        description=f"Transferred {count} {object_type} record(s) from user {from_user_id} to {to_user_id}",
        user=request.user,
        metadata={
            "object_type": object_type,
            "from_user_id": int(from_user_id),
            "to_user_id": int(to_user_id),
            "count": count,
            "ids": ids[:100],
            "truncated_ids": len(ids) > 100,
        },
    )
    return Response({"success": True, "count": count})


def _serialize_target(target: ScrapeTarget) -> dict:
    return {
        "id": target.id,
        "name": target.name,
        "enabled": target.enabled,
        "target_type": target.target_type,
        "start_url": target.start_url,
        "run_every_minutes": target.run_every_minutes,
        "last_run_at": target.last_run_at.isoformat() if target.last_run_at else None,
        "owner_id": target.owner_id,
    }


def _serialize_scrape_run(run: ScrapeRun) -> dict:
    return {
        "id": run.id,
        "target": run.target_id,
        "target_name": run.target.name if run.target_id else "",
        "trigger": run.trigger,
        "status": run.status,
        "status_display": run.get_status_display(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "task_id": run.task_id,
        "error_text": run.error_text,
        "item_count": run.item_count,
        "created_leads": run.created_leads,
        "updated_leads": run.updated_leads,
        "owner_id": run.owner_id,
    }


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_targets_list(request: Request) -> Response:
    qs = ScrapeTarget.objects.all().order_by("name")
    enabled = request.query_params.get("enabled")
    if enabled in {"true", "false"}:
        qs = qs.filter(enabled=(enabled == "true"))
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    rows = [_serialize_target(t) for t in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_target_trigger(request: Request, target_id: int) -> Response:
    try:
        target = ScrapeTarget.objects.get(id=target_id)
    except ScrapeTarget.DoesNotExist:
        return Response({"success": False, "error": "Target not found"}, status=status.HTTP_404_NOT_FOUND)

    task = scrape_target.delay(target_id=target.id, trigger="manual", initiated_by_id=request.user.id)
    log_activity(
        action="admin_scrape_triggered",
        object_type="target",
        object_id=target.id,
        description=f"Admin triggered scrape for {target.name}",
        user=request.user,
        metadata={"task_id": task.id},
    )
    return Response({"success": True, "message": f"Scrape triggered for {target.name}", "task_id": task.id})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_runs_list(request: Request) -> Response:
    qs = ScrapeRun.objects.select_related("target").order_by("-started_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    target_id = request.query_params.get("target_id")
    if target_id and str(target_id).isdigit():
        qs = qs.filter(target_id=int(target_id))
    rows = [_serialize_scrape_run(r) for r in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_run_retry(request: Request, run_id: int) -> Response:
    try:
        run = ScrapeRun.objects.select_related("target").get(id=run_id)
    except ScrapeRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    if run.status != ScrapeRunStatus.FAILED:
        return Response(
            {"success": False, "error": "Only failed runs can be retried."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    task = scrape_target.delay(target_id=run.target_id, trigger="manual", initiated_by_id=request.user.id)
    log_activity(
        action="admin_scrape_retry",
        object_type="run",
        object_id=run.id,
        description=f"Admin retried scrape run #{run.id}",
        user=request.user,
        metadata={"task_id": task.id, "target_id": run.target_id},
    )
    return Response({"success": True, "message": "Retry queued", "task_id": task.id})


def _serialize_crawl_source(source: CrawlSource) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "discovery_query": source.discovery_query,
        "source_type": source.source_type,
        "enabled": source.enabled,
        "priority": source.priority,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "owner_id": source.owner_id,
    }


def _serialize_domain(domain: DiscoveredDomain) -> dict:
    return {
        "id": domain.id,
        "domain": domain.domain,
        "source_url": domain.source_url,
        "source": domain.source_id,
        "source_name": domain.source.name if domain.source_id else "",
        "crawl_status": domain.crawl_status,
        "crawl_attempts": domain.crawl_attempts,
        "priority": domain.priority,
        "first_seen_at": domain.first_seen_at.isoformat() if domain.first_seen_at else None,
        "last_crawled_at": domain.last_crawled_at.isoformat() if domain.last_crawled_at else None,
        "next_attempt_at": domain.next_attempt_at.isoformat() if domain.next_attempt_at else None,
        "error_text": domain.error_text,
        "owner_id": domain.owner_id,
    }


def _serialize_crawl_run(run: CrawlRun) -> dict:
    return serialize_crawl_session_run(run, include_owner=True)


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_sessions_active(request: Request) -> Response:
    rows = [serialize_crawl_session_run(r, include_owner=True) for r in active_crawl_sessions_qs()]
    return Response({"success": True, "data": rows})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_session_stop(request: Request, run_id: int) -> Response:
    from dashboard.api.views import _cancel_crawl_run

    try:
        run = CrawlRun.objects.get(id=run_id)
    except CrawlRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)

    if run.trigger != CrawlRunTrigger.SESSION:
        return Response(
            {"success": False, "error": "Not a crawl session run."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if run.status != CrawlRunStatus.RUNNING:
        return Response({"success": False, "error": "Session is not running."}, status=status.HTTP_400_BAD_REQUEST)

    _cancel_crawl_run(run, error_text="Cancelled by admin.", notify_session=True)
    log_activity(
        action="crawl_triggered",
        object_type="crawl_run",
        object_id=run.id,
        description=f"Admin stopped crawl session #{run.id}",
        user=request.user,
    )
    return Response({"success": True, "message": f"Session #{run.id} stopped."})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_sessions_active(request: Request) -> Response:
    rows = [serialize_scrape_session(s, include_owner=True) for s in active_scrape_sessions_qs()]
    return Response({"success": True, "data": rows})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def scraper_session_stop(request: Request, session_id: int) -> Response:
    from scraper.models import ScrapeSession, ScrapeSessionStatus
    from scraper.tasks import finalize_scrape_session

    try:
        session = ScrapeSession.objects.get(id=session_id)
    except ScrapeSession.DoesNotExist:
        return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    if session.status != ScrapeSessionStatus.RUNNING:
        return Response({"success": False, "error": "Session is not running."}, status=status.HTTP_400_BAD_REQUEST)

    if session.coordinator_task_id:
        try:
            current_app.control.revoke(session.coordinator_task_id, terminate=False)
        except Exception:
            pass
    finalize_scrape_session.delay(session.id, reason="cancelled", error="Cancelled by admin.")
    log_activity(
        action="scrape_triggered",
        object_type="scrape_session",
        object_id=session.id,
        description=f"Admin stopped scrape session #{session.id}",
        user=request.user,
    )
    return Response({"success": True, "message": f"Session #{session.id} stopped."})


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_schedules_list(request: Request) -> Response:
    if request.method == "POST":
        owner_id = request.data.get("owner_id")
        if not owner_id:
            return Response(
                {"success": False, "error": "owner_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            owner = User.objects.get(id=int(owner_id))
        except (User.DoesNotExist, TypeError, ValueError):
            return Response({"success": False, "error": "Invalid owner_id."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CrawlScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=owner)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

    qs = CrawlSchedule.objects.select_related("owner").order_by("-created_at")
    owner_id = request.query_params.get("owner_id")
    if owner_id:
        qs = qs.filter(owner_id=owner_id)
    enabled = request.query_params.get("enabled")
    if enabled in {"true", "false"}:
        qs = qs.filter(enabled=(enabled == "true"))
    rows = CrawlScheduleSerializer(qs, many=True).data
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_schedule_detail(request: Request, schedule_id: int) -> Response:
    try:
        schedule = CrawlSchedule.objects.select_related("owner").get(id=schedule_id)
    except CrawlSchedule.DoesNotExist:
        return Response({"success": False, "error": "Schedule not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response({"success": True, "data": CrawlScheduleSerializer(schedule).data})

    if request.method == "DELETE":
        schedule.delete()
        return Response({"success": True, "message": "Schedule deleted."})

    serializer = CrawlScheduleSerializer(schedule, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"success": True, "data": serializer.data})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_sources_list(request: Request) -> Response:
    qs = CrawlSource.objects.all().order_by("priority", "id")
    source_type = (request.query_params.get("source_type") or "").strip()
    if source_type:
        qs = qs.filter(source_type=source_type)
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    rows = [_serialize_crawl_source(s) for s in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_source_update(request: Request, source_id: int) -> Response:
    try:
        source = CrawlSource.objects.get(id=source_id)
    except CrawlSource.DoesNotExist:
        return Response({"success": False, "error": "Source not found"}, status=status.HTTP_404_NOT_FOUND)

    before = {
        "enabled": source.enabled,
        "priority": source.priority,
        "name": source.name,
        "discovery_query": source.discovery_query,
    }

    for key in ["enabled", "name", "discovery_query", "source_type", "priority"]:
        if key in request.data:
            setattr(source, key, request.data.get(key))
    source.save()

    log_activity(
        action="target_updated",
        object_type="crawl_source",
        object_id=source.id,
        description=f"Updated crawl source {source.name}",
        user=request.user,
        metadata={"before": before, "after": _serialize_crawl_source(source)},
    )
    return Response({"success": True, "data": _serialize_crawl_source(source)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_domains_list(request: Request) -> Response:
    qs = DiscoveredDomain.objects.select_related("source").all().order_by("-first_seen_at")
    crawl_status = (request.query_params.get("crawl_status") or "").strip()
    if crawl_status:
        qs = qs.filter(crawl_status=crawl_status)
    source_id = (request.query_params.get("source_id") or "").strip()
    if source_id.isdigit():
        qs = qs.filter(source_id=int(source_id))
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(domain__icontains=search)
    rows = [_serialize_domain(d) for d in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_domain_trigger(request: Request, domain_id: int) -> Response:
    try:
        domain = DiscoveredDomain.objects.get(id=domain_id)
    except DiscoveredDomain.DoesNotExist:
        return Response({"success": False, "error": "Domain not found"}, status=status.HTTP_404_NOT_FOUND)

    run = CrawlRun.objects.create(
        owner_id=domain.owner_id,
        trigger=CrawlRunTrigger.MANUAL,
        status=CrawlRunStatus.RUNNING,
        started_at=timezone.now(),
        domains_queued=1,
    )
    crawl_domain_task.delay(domain_id=domain.id, run_id=run.id, owner_id=domain.owner_id)
    log_activity(
        action="crawl_triggered",
        object_type="crawl_domain",
        object_id=domain.id,
        description=f"Admin triggered crawl for domain {domain.domain}",
        user=request.user,
        metadata={"run_id": run.id},
    )
    return Response({"success": True, "run_id": run.id})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_domains_reset_failed(request: Request) -> Response:
    ids = request.data.get("domain_ids") or []
    qs = DiscoveredDomain.objects.filter(crawl_status="failed")
    if ids:
        qs = qs.filter(id__in=ids)
    count = qs.update(crawl_status="pending", error_text="", next_attempt_at=None)
    log_activity(
        action="crawl_triggered",
        object_type="crawl_domain",
        object_id=0,
        description=f"Admin reset {count} failed domain(s) to pending",
        user=request.user,
        metadata={"count": count},
    )
    return Response({"success": True, "count": count})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_runs_list(request: Request) -> Response:
    qs = CrawlRun.objects.all().order_by("-started_at")
    status_filter = (request.query_params.get("status") or "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    trigger_filter = (request.query_params.get("trigger") or "").strip()
    if trigger_filter:
        qs = qs.filter(trigger=trigger_filter)
    rows = [_serialize_crawl_run(r) for r in qs]
    return Response({"success": True, "data": _pagination(request, rows)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_run_cancel(request: Request, run_id: int) -> Response:
    try:
        run = CrawlRun.objects.get(id=run_id)
    except CrawlRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    if run.status != CrawlRunStatus.RUNNING:
        return Response({"success": False, "error": "Run is not currently running."}, status=status.HTTP_400_BAD_REQUEST)

    from dashboard.api.views import _cancel_crawl_run

    if run.trigger == CrawlRunTrigger.SESSION:
        _cancel_crawl_run(run, error_text="Cancelled by admin.")
    else:
        if run.task_id:
            try:
                current_app.control.revoke(run.task_id, terminate=False)
            except Exception:
                pass
        run.status = CrawlRunStatus.FAILED
        run.error_text = "Cancelled by admin."
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_text", "finished_at"])
    log_activity(
        action="crawl_triggered",
        object_type="crawl_run",
        object_id=run.id,
        description=f"Admin cancelled crawl run #{run.id}",
        user=request.user,
    )
    return Response({"success": True, "message": f"Run #{run.id} cancelled."})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_runs_cancel_all(request: Request) -> Response:
    running = list(CrawlRun.objects.filter(status=CrawlRunStatus.RUNNING))
    cancelled = 0
    for run in running:
        if run.trigger == CrawlRunTrigger.SESSION:
            from dashboard.api.views import _cancel_crawl_run

            _cancel_crawl_run(run, error_text="Cancelled in batch by admin.")
        else:
            if run.task_id:
                try:
                    current_app.control.revoke(run.task_id, terminate=False)
                except Exception:
                    pass
            run.status = CrawlRunStatus.FAILED
            run.error_text = "Cancelled in batch by admin."
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_text", "finished_at"])
        cancelled += 1
    log_activity(
        action="crawl_triggered",
        object_type="crawl_run",
        object_id=0,
        description=f"Admin cancelled all running crawl runs ({cancelled})",
        user=request.user,
        metadata={"cancelled": cancelled},
    )
    return Response({"success": True, "cancelled": cancelled})


def _paginate_queryset(request: Request, qs, serializer_cls):
    page = _parse_positive_int(request.query_params.get("page"), field="page", default=1, minimum=1)
    page_size = _parse_positive_int(
        request.query_params.get("page_size"),
        field="page_size",
        default=25,
        minimum=1,
        maximum=100,
    )
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    chunk = qs[start:end]
    return {
        "items": serializer_cls(chunk, many=True).data,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": end < total,
    }


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def admin_ai_search_jobs(request: Request) -> Response:
    if request.method == "POST":
        if not _get_serper_api_key() and not (getattr(settings, "GEMINI_API_KEY", None) or "").strip():
            return Response(
                {
                    "success": False,
                    "error": (
                        "AI search is not configured. Set GEMINI_API_KEY and/or SERPER_API_KEY on the server."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw_owner = request.data.get("owner_id")
        if raw_owner is not None and str(raw_owner).strip() != "":
            try:
                owner_id = int(raw_owner)
            except (TypeError, ValueError):
                return Response(
                    {"success": False, "error": "owner_id must be a valid integer user id when provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                owner = User.objects.get(pk=owner_id)
            except User.DoesNotExist:
                return Response({"success": False, "error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            owner = request.user

        seed_topic = (request.data.get("seed_topic") or "").strip()
        if not seed_topic:
            return Response(
                {"success": False, "error": "seed_topic is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        industry = (request.data.get("industry") or "").strip()[:200]
        region = (request.data.get("region") or "").strip()[:200]
        job = AISearchJob.objects.create(
            owner=owner,
            seed_topic=seed_topic[:500],
            industry=industry,
            region=region,
            status="pending",
        )
        run_ai_search_job.delay(job.id)
        log_activity(
            action="crawl_triggered",
            object_type="ai_search_job",
            object_id=job.id,
            description=(
                f"Admin AI search ({request.user.get_username()} → owner {owner.get_username()}): "
                f"{job.seed_topic[:50]}"
            ),
            user=request.user,
            metadata={"job_owner_id": owner.id, "initiated_by_id": request.user.id},
        )
        return Response(
            {"success": True, "data": AISearchJobSerializer(job).data},
            status=status.HTTP_201_CREATED,
        )

    qs = AISearchJob.objects.select_related("owner").all().order_by("-created_at")
    oid = (request.query_params.get("owner_id") or "").strip()
    if oid.isdigit():
        qs = qs.filter(owner_id=int(oid))
    return Response({"success": True, "data": _paginate_queryset(request, qs, AISearchJobSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def admin_ai_search_job_detail(request: Request, job_id: int) -> Response:
    try:
        job = AISearchJob.objects.select_related("owner").get(pk=job_id)
    except AISearchJob.DoesNotExist:
        return Response({"success": False, "error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    res_qs = job.results.all().order_by("-created_at", "-id")
    return Response(
        {
            "success": True,
            "data": {
                "job": AISearchJobSerializer(job).data,
                "results": _paginate_queryset(request, res_qs, AISearchResultSerializer),
            },
        }
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def admin_ai_search_result_promote(request: Request, result_id: int) -> Response:
    try:
        result = AISearchResult.objects.select_related("job", "job__owner").get(pk=result_id)
    except AISearchResult.DoesNotExist:
        return Response({"success": False, "error": "Result not found"}, status=status.HTTP_404_NOT_FOUND)

    from crawler.services.ai_page_extract import result_promotable

    if not result_promotable(result):
        return Response(
            {
                "success": False,
                "error": "Result score is below the minimum required for promotion.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    prospect, created = promote_ai_search_result_to_prospect(
        result,
        owner_id=result.job.owner_id,
    )
    result.refresh_from_db()
    if created:
        log_activity(
            action="prospect_created",
            object_type="prospect",
            object_id=prospect.id,
            description=(
                f"Admin promoted AI search result #{result.id} ({result.domain}) "
                f"to prospect for owner {result.job.owner.get_username()}"
            ),
            user=request.user,
        )
    return Response(
        {
            "success": True,
            "data": {
                "prospect_id": prospect.id,
                "created": created,
                "result": AISearchResultSerializer(result).data,
            },
        }
    )
