from __future__ import annotations

import os
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunDomainResult,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSchedule,
    CrawlSource,
    DiscoveredDomain,
    EventProspect,
)
from crawler.discovery import _get_serper_api_key
from crawler.services.crawl_session import SessionStartError, start_crawl_session_for_user
from crawler.services.promote_ai_result import promote_ai_search_result_to_prospect
from crawler.tasks import (
    crawl_domain_task,
    discover_websites_task,
    run_ai_search_job,
)
from dashboard.api.decorators import dashboard_api_view
from dashboard.api.permissions import IsDashboardPortalUser
from dashboard.api.serializers import (
    AISearchJobSerializer,
    AISearchResultSerializer,
    CrawlSessionStartSerializer,
    CrawlScheduleSerializer,
    CrawlSourceSerializer,
    CrawlRunDomainResultSerializer,
    DiscoveredDomainSerializer,
    CrawlRunSerializer,
    EventProspectSerializer,
    LeadSerializer,
    LeadWriteSerializer,
    ProspectSerializer,
    ProspectWriteSerializer,
    ScrapeRunSerializer,
    ScrapeSessionSerializer,
    ScrapeSessionStartSerializer,
    ScrapeTargetSerializer,
)
from dashboard.api.duplicates import find_lead_duplicates, find_prospect_duplicates
from dashboard.api.metrics_quality import build_discovery_drop_metrics, build_quality_metrics
from dashboard.models import Notification
from dashboard.utils import log_activity, notify_crawl_session
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.models import ScrapeSession, ScrapeSessionStatus
from scraper.services.scrape_session import SessionStartError as ScrapeSessionStartError
from scraper.services.scrape_session import start_scrape_session_for_user
from scraper.tasks import finalize_scrape_session, scrape_target


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


def _pagination(request: Request, queryset, serializer_cls):
    page = _parse_positive_int(request.query_params.get("page"), field="page", default=1, minimum=1)
    page_size = _parse_positive_int(
        request.query_params.get("page_size"),
        field="page_size",
        default=25,
        minimum=1,
        maximum=100,
    )
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    rows = queryset[start:end]
    return {
        "items": serializer_cls(rows, many=True).data,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": end < total,
    }


def _is_admin_user(request: Request) -> bool:
    return bool(request.user and request.user.is_superuser)


def _owned_qs(request: Request, qs, owner_field: str = "owner"):
    if _is_admin_user(request):
        return qs
    return qs.filter(**{owner_field: request.user})


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def targets_list(request: Request) -> Response:
    if request.method == "POST":
        serializer = ScrapeTargetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        log_activity(
            action="target_created",
            object_type="target",
            object_id=serializer.instance.id,
            description=f"Created scrape target {serializer.instance.name}",
            user=request.user,
        )
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

    qs = _owned_qs(request, ScrapeTarget.objects.all()).order_by("name")
    enabled = request.query_params.get("enabled")
    if enabled in {"true", "false"}:
        qs = qs.filter(enabled=(enabled == "true"))
    return Response({"success": True, "data": _pagination(request, qs, ScrapeTargetSerializer)})


@dashboard_api_view(["GET", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def target_detail(request: Request, target_id: int) -> Response:
    try:
        target = _owned_qs(request, ScrapeTarget.objects.all()).get(id=target_id)
    except ScrapeTarget.DoesNotExist:
        return Response({"success": False, "error": "Target not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response({"success": True, "data": ScrapeTargetSerializer(target).data})

    serializer = ScrapeTargetSerializer(target, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    log_activity(
        action="target_updated",
        object_type="target",
        object_id=target.id,
        description=f"Updated scrape target {target.name}",
        user=request.user,
    )
    return Response({"success": True, "data": serializer.data})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def trigger_all_targets(request: Request) -> Response:
    targets = list(_owned_qs(request, ScrapeTarget.objects.filter(enabled=True)))
    if not targets:
        return Response({"success": False, "error": "No enabled targets to scrape."}, status=status.HTTP_400_BAD_REQUEST)
    task_ids: list[str] = []
    for target in targets:
        task = scrape_target.delay(target_id=target.id, trigger="manual", initiated_by_id=request.user.id)
        task_ids.append(str(task.id))
        log_activity(
            action="scrape_triggered",
            object_type="target",
            object_id=target.id,
            description=f"Bulk scrape triggered for {target.name}",
            user=request.user,
            metadata={"task_id": task.id, "bulk": True},
        )
    return Response(
        {
            "success": True,
            "message": f"Queued scrapes for {len(targets)} enabled target(s).",
            "count": len(targets),
            "task_ids": task_ids,
        }
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def trigger_target(request: Request, target_id: int) -> Response:
    try:
        target = _owned_qs(request, ScrapeTarget.objects.all()).get(id=target_id)
    except ScrapeTarget.DoesNotExist:
        return Response({"success": False, "error": "Target not found"}, status=status.HTTP_404_NOT_FOUND)
    task = scrape_target.delay(target_id=target.id, trigger="manual", initiated_by_id=request.user.id)
    log_activity(
        action="scrape_triggered",
        object_type="target",
        object_id=target.id,
        description=f"Scrape triggered for {target.name}",
        user=request.user,
        metadata={"task_id": task.id},
    )
    return Response({"success": True, "message": f"Scrape triggered for {target.name}", "task_id": task.id})


def _active_scrape_session_for_user(user):
    now = timezone.now()
    return (
        ScrapeSession.objects.filter(
            owner=user,
            status=ScrapeSessionStatus.RUNNING,
            ends_at__gt=now,
        )
        .order_by("-started_at")
        .first()
    )


def _cancel_scrape_session(session: ScrapeSession, *, error_text: str) -> None:
    if session.coordinator_task_id:
        try:
            current_app.control.revoke(session.coordinator_task_id, terminate=False)
        except Exception:
            pass
    finalize_scrape_session.delay(session.id, reason="cancelled", error=error_text)


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_session_start(request: Request) -> Response:
    ser = ScrapeSessionStartSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    duration_minutes = int(ser.validated_data["duration_minutes"])

    try:
        session = start_scrape_session_for_user(request.user, duration_minutes)
    except ScrapeSessionStartError as exc:
        return Response(
            {"success": False, "error": exc.message},
            status=exc.status_code,
        )

    return Response(
        {
            "success": True,
            "session_id": session.id,
            "ends_at": session.ends_at.isoformat() if session.ends_at else None,
            "message": f"Scrape session started for {duration_minutes} minutes.",
            "data": ScrapeSessionSerializer(session).data,
        },
        status=status.HTTP_201_CREATED,
    )


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_session_active(request: Request) -> Response:
    session = _active_scrape_session_for_user(request.user)
    if not session:
        return Response({"success": True, "data": None})
    return Response({"success": True, "data": ScrapeSessionSerializer(session).data})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_session_stop(request: Request, session_id: int) -> Response:
    try:
        session = _owned_qs(request, ScrapeSession.objects.all()).get(id=session_id)
    except ScrapeSession.DoesNotExist:
        return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    if session.status != ScrapeSessionStatus.RUNNING:
        return Response({"success": False, "error": "Session is not running."}, status=status.HTTP_400_BAD_REQUEST)

    _cancel_scrape_session(session, error_text="Cancelled by user.")
    return Response({"success": True, "message": f"Session #{session.id} stopped."})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_runs_list(request: Request) -> Response:
    qs = _owned_qs(request, ScrapeRun.objects.select_related("target")).order_by("-started_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    target_id = request.query_params.get("target_id")
    if target_id:
        qs = qs.filter(target_id=target_id)
    return Response({"success": True, "data": _pagination(request, qs, ScrapeRunSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_run_detail(request: Request, run_id: int) -> Response:
    try:
        run = _owned_qs(request, ScrapeRun.objects.select_related("target")).get(id=run_id)
    except ScrapeRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True, "data": ScrapeRunSerializer(run).data})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def scrape_run_retry(request: Request, run_id: int) -> Response:
    try:
        run = _owned_qs(request, ScrapeRun.objects.select_related("target")).get(id=run_id)
    except ScrapeRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    if run.status != ScrapeRunStatus.FAILED:
        return Response(
            {"success": False, "error": "Only failed runs can be retried."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    task = scrape_target.delay(target_id=run.target_id, trigger="manual", initiated_by_id=request.user.id)
    return Response({"success": True, "message": "Retry queued", "task_id": task.id})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_runs_list(request: Request) -> Response:
    qs = _owned_qs(request, CrawlRun.objects.all()).order_by("-started_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    trigger_filter = request.query_params.get("trigger")
    if trigger_filter:
        qs = qs.filter(trigger=trigger_filter)
    return Response({"success": True, "data": _pagination(request, qs, CrawlRunSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_run_detail(request: Request, run_id: int) -> Response:
    try:
        run = _owned_qs(request, CrawlRun.objects.all()).get(id=run_id)
    except CrawlRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    result_qs = CrawlRunDomainResult.objects.filter(crawl_run_id=run.id)
    summary = {
        "total_domains": result_qs.count(),
        "failed_domains": result_qs.filter(Q(state="failed") | Q(crawl_succeeded=False)).count(),
        "prospects_created": result_qs.filter(prospect_created=True).count(),
        "prospects_updated": result_qs.filter(prospect_updated=True).count(),
    }
    data = CrawlRunSerializer(run).data
    data["summary"] = summary
    return Response({"success": True, "data": data})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_run_domain_results(request: Request, run_id: int) -> Response:
    if not _owned_qs(request, CrawlRun.objects.all()).filter(id=run_id).exists():
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    qs = CrawlRunDomainResult.objects.select_related("domain", "crawl_run").filter(crawl_run_id=run_id).order_by("-updated_at")
    state = request.query_params.get("state")
    if state:
        qs = qs.filter(state=state)
    only_errors = request.query_params.get("errors_only")
    if only_errors == "true":
        qs = qs.filter(Q(state="failed") | Q(crawl_error__gt=""))
    return Response({"success": True, "data": _pagination(request, qs, CrawlRunDomainResultSerializer)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_trigger(request: Request) -> Response:
    task = discover_websites_task.delay(initiated_by_id=request.user.id)
    return Response({"success": True, "message": "Crawler discovery queued", "task_id": task.id})


def _active_crawl_session_for_user(user):
    now = timezone.now()
    return (
        CrawlRun.objects.filter(
            owner=user,
            status=CrawlRunStatus.RUNNING,
            trigger=CrawlRunTrigger.SESSION,
            ends_at__gt=now,
        )
        .order_by("-started_at")
        .first()
    )


def _cancel_crawl_run(run: CrawlRun, *, error_text: str, notify_session: bool = True) -> None:
    if run.task_id:
        try:
            current_app.control.revoke(run.task_id, terminate=False)
        except Exception:
            pass
    if run.coordinator_task_id:
        try:
            current_app.control.revoke(run.coordinator_task_id, terminate=False)
        except Exception:
            pass

    was_session = run.trigger == CrawlRunTrigger.SESSION and run.status == CrawlRunStatus.RUNNING
    run.status = CrawlRunStatus.FAILED
    run.error_text = error_text
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_text", "finished_at"])

    if notify_session and was_session and run.owner_id:
        owner = run.owner
        if owner:
            notify_crawl_session(owner, run, "cancelled")


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_session_start(request: Request) -> Response:
    ser = CrawlSessionStartSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    duration_minutes = int(ser.validated_data["duration_minutes"])

    try:
        run = start_crawl_session_for_user(request.user, duration_minutes)
    except SessionStartError as exc:
        return Response(
            {"success": False, "error": exc.message},
            status=exc.status_code,
        )

    return Response(
        {
            "success": True,
            "run_id": run.id,
            "ends_at": run.ends_at.isoformat() if run.ends_at else None,
            "message": f"Crawl session started for {duration_minutes} minutes.",
            "data": CrawlRunSerializer(run).data,
        },
        status=status.HTTP_201_CREATED,
    )


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_session_active(request: Request) -> Response:
    run = _active_crawl_session_for_user(request.user)
    if not run:
        return Response({"success": True, "data": None})
    return Response({"success": True, "data": CrawlRunSerializer(run).data})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_session_stop(request: Request, run_id: int) -> Response:
    try:
        run = _owned_qs(request, CrawlRun.objects.all()).get(id=run_id)
    except CrawlRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)

    if run.trigger != CrawlRunTrigger.SESSION:
        return Response(
            {"success": False, "error": "Not a crawl session run."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if run.status != CrawlRunStatus.RUNNING:
        return Response({"success": False, "error": "Session is not running."}, status=status.HTTP_400_BAD_REQUEST)

    _cancel_crawl_run(run, error_text="Cancelled by user.")
    return Response({"success": True, "message": f"Session #{run.id} stopped."})


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_schedules_list(request: Request) -> Response:
    if request.method == "POST":
        serializer = CrawlScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

    qs = _owned_qs(request, CrawlSchedule.objects.all()).order_by("-created_at")
    enabled = request.query_params.get("enabled")
    if enabled in {"true", "false"}:
        qs = qs.filter(enabled=(enabled == "true"))
    return Response({"success": True, "data": _pagination(request, qs, CrawlScheduleSerializer)})


@dashboard_api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_schedule_detail(request: Request, schedule_id: int) -> Response:
    try:
        schedule = _owned_qs(request, CrawlSchedule.objects.all()).get(id=schedule_id)
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


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_run_cancel(request: Request, run_id: int) -> Response:
    try:
        run = _owned_qs(request, CrawlRun.objects.all()).get(id=run_id)
    except CrawlRun.DoesNotExist:
        return Response({"success": False, "error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)

    if run.status != CrawlRunStatus.RUNNING:
        return Response({"success": False, "error": "Run is not currently running."}, status=status.HTTP_400_BAD_REQUEST)

    if run.trigger == CrawlRunTrigger.SESSION:
        _cancel_crawl_run(run, error_text="Cancelled by staff user.")
        return Response({"success": True, "message": f"Run #{run.id} cancelled."})

    if run.task_id:
        try:
            current_app.control.revoke(run.task_id, terminate=False)
        except Exception:
            pass

    run.status = CrawlRunStatus.FAILED
    run.error_text = "Cancelled by staff user."
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_text", "finished_at"])
    return Response({"success": True, "message": f"Run #{run.id} cancelled."})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_runs_cancel_all(request: Request) -> Response:
    running = list(_owned_qs(request, CrawlRun.objects.all()).filter(status=CrawlRunStatus.RUNNING))
    cancelled = 0
    for run in running:
        if run.trigger == CrawlRunTrigger.SESSION:
            _cancel_crawl_run(run, error_text="Cancelled in batch by staff user.")
        else:
            if run.task_id:
                try:
                    current_app.control.revoke(run.task_id, terminate=False)
                except Exception:
                    pass
            run.status = CrawlRunStatus.FAILED
            run.error_text = "Cancelled in batch by staff user."
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_text", "finished_at"])
        cancelled += 1
    return Response({"success": True, "cancelled": cancelled})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_sources_list(request: Request) -> Response:
    qs = _owned_qs(request, CrawlSource.objects.all()).order_by("-created_at")
    source_type = request.query_params.get("source_type")
    if source_type:
        qs = qs.filter(source_type=source_type)
    return Response({"success": True, "data": _pagination(request, qs, CrawlSourceSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_domains_list(request: Request) -> Response:
    qs = _owned_qs(request, DiscoveredDomain.objects.select_related("source")).order_by("-first_seen_at")
    crawl_status = request.query_params.get("crawl_status")
    if crawl_status:
        qs = qs.filter(crawl_status=crawl_status)
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(domain__icontains=search)
    return Response({"success": True, "data": _pagination(request, qs, DiscoveredDomainSerializer)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawl_domain_trigger(request: Request, domain_id: int) -> Response:
    try:
        domain = _owned_qs(request, DiscoveredDomain.objects.all()).get(id=domain_id)
    except DiscoveredDomain.DoesNotExist:
        return Response({"success": False, "error": "Domain not found"}, status=status.HTTP_404_NOT_FOUND)

    run = CrawlRun.objects.create(
        owner=request.user,
        trigger=CrawlRunTrigger.MANUAL,
        status=CrawlRunStatus.RUNNING,
        started_at=timezone.now(),
        domains_queued=1,
    )
    crawl_domain_task.delay(domain_id=int(domain.id), run_id=run.id, owner_id=request.user.id)
    return Response({"success": True, "run_id": run.id})


def _apply_search(qs, request: Request, fields: list[str]):
    search = (request.query_params.get("search") or "").strip()
    if not search:
        return qs
    q = Q()
    for field in fields:
        q |= Q(**{f"{field}__icontains": search})
    return qs.filter(q)


def _apply_prospect_list_filters(request: Request, qs):
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    source_filter = (request.query_params.get("source") or "").strip()
    if source_filter:
        qs = qs.filter(source_name__icontains=source_filter)

    min_score_raw = (request.query_params.get("min_score") or "").strip()
    if min_score_raw:
        try:
            min_score = int(min_score_raw)
            qs = qs.filter(raw_payload__translation_need_score__gte=min_score)
        except ValueError as exc:
            raise ValidationError({"min_score": "min_score must be an integer."}) from exc

    qs = _apply_search(qs, request, ["company", "event_name", "email", "website", "source_name"])

    sort = (request.query_params.get("sort") or "created_at").strip().lower()
    if sort == "score":
        qs = qs.order_by("-raw_payload__translation_need_score", "-created_at")
    else:
        qs = qs.order_by("-created_at")
    return qs


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospects_list(request: Request) -> Response:
    if request.method == "POST":
        serializer = ProspectWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prospect = serializer.save(owner=request.user)
        log_activity(
            action="prospect_created",
            object_type="prospect",
            object_id=prospect.id,
            description=f"Manually created prospect #{prospect.id}",
            user=request.user,
        )
        return Response(
            {"success": True, "data": ProspectSerializer(prospect).data},
            status=status.HTTP_201_CREATED,
        )

    qs = _owned_qs(request, Prospect.objects.all())
    qs = _apply_prospect_list_filters(request, qs)
    return Response({"success": True, "data": _pagination(request, qs, ProspectSerializer)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospects_bulk_contacted(request: Request) -> Response:
    ids = request.data.get("prospect_ids") or []
    count = _owned_qs(request, Prospect.objects.all()).filter(id__in=ids, status=ProspectStatus.NEW).update(
        status=ProspectStatus.CONTACTED,
        contacted_at=timezone.now(),
    )
    return Response({"success": True, "count": count})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospects_bulk_convert(request: Request) -> Response:
    ids = request.data.get("prospect_ids") or []
    prospects = _owned_qs(request, Prospect.objects.all()).filter(id__in=ids, status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED])
    converted = 0
    errors: list[str] = []
    for p in prospects:
        try:
            p.convert_to_lead()
            converted += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    return Response({"success": True, "count": converted, "errors": errors})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospects_bulk_reject(request: Request) -> Response:
    ids = request.data.get("prospect_ids") or []
    count = _owned_qs(request, Prospect.objects.all()).filter(
        id__in=ids, status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED]
    ).update(status=ProspectStatus.REJECTED, rejected_at=timezone.now())
    return Response({"success": True, "count": count})


@dashboard_api_view(["GET", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_detail(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "PATCH":
        serializer = ProspectWriteSerializer(prospect, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            action="prospect_updated",
            object_type="prospect",
            object_id=prospect.id,
            description=f"Updated prospect #{prospect.id}",
            user=request.user,
        )
        return Response({"success": True, "data": ProspectSerializer(prospect).data})

    return Response({"success": True, "data": ProspectSerializer(prospect).data})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_duplicates(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    rows = find_prospect_duplicates(prospect, _owned_qs(request, Prospect.objects.all()))
    return Response({"success": True, "data": {"items": rows, "total": len(rows)}})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_mark_contacted(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    if prospect.status != ProspectStatus.NEW:
        return Response({"success": False, "error": "Only NEW prospects can be marked contacted."}, status=400)
    prospect.mark_contacted()
    return Response({"success": True})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_convert(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    try:
        lead = prospect.convert_to_lead()
    except Exception as exc:  # noqa: BLE001
        return Response({"success": False, "error": str(exc)}, status=400)
    return Response({"success": True, "lead_id": lead.id})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_reject(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    reason = (request.data.get("reason") or "").strip()
    prospect.mark_rejected(reason=reason)
    return Response({"success": True})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_enrich(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)

    from scraper.services.enrichment import enrich_prospect

    platform = (request.data.get("platform") or "generic").strip() or "generic"
    use_playwright = bool(request.data.get("use_playwright"))
    force = bool(request.data.get("force"))

    result = enrich_prospect(prospect.id, platform, use_playwright, force=force)
    if not result.get("success"):
        return Response(
            {"success": False, "error": result.get("error", "Enrichment failed")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    prospect.refresh_from_db()
    return Response(
        {
            "success": True,
            "skipped": bool(result.get("skipped")),
            "updated_fields": result.get("updated_fields") or [],
            "data": ProspectSerializer(prospect).data,
        }
    )


def _apply_event_prospect_list_filters(request: Request, qs):
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    min_score_raw = (request.query_params.get("min_score") or "").strip()
    if min_score_raw:
        try:
            qs = qs.filter(translation_need_score__gte=int(min_score_raw))
        except ValueError as exc:
            raise ValidationError({"min_score": "min_score must be an integer."}) from exc

    qs = _apply_search(qs, request, ["event_name", "organizer_name", "organizer_domain", "event_location"])

    sort = (request.query_params.get("sort") or "urgency").strip().lower()
    if sort == "date":
        qs = qs.order_by("event_date", "-urgency_score")
    elif sort == "score":
        qs = qs.order_by("-translation_need_score", "-urgency_score")
    else:
        qs = qs.order_by("-urgency_score", "event_date")
    return qs


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def event_prospects_list(request: Request) -> Response:
    qs = _owned_qs(request, EventProspect.objects.all())
    qs = _apply_event_prospect_list_filters(request, qs)
    return Response({"success": True, "data": _pagination(request, qs, EventProspectSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def event_prospect_detail(request: Request, event_prospect_id: int) -> Response:
    try:
        row = _owned_qs(request, EventProspect.objects.all()).get(id=event_prospect_id)
    except EventProspect.DoesNotExist:
        return Response({"success": False, "error": "Event prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True, "data": EventProspectSerializer(row).data})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def event_prospect_promote(request: Request, event_prospect_id: int) -> Response:
    try:
        row = _owned_qs(request, EventProspect.objects.all()).get(id=event_prospect_id)
    except EventProspect.DoesNotExist:
        return Response({"success": False, "error": "Event prospect not found"}, status=status.HTTP_404_NOT_FOUND)

    if row.status in ("expired", "irrelevant"):
        return Response({"success": False, "error": f"Cannot promote event prospect with status {row.status}."}, status=400)

    from crawler.services.promote_event_prospect import promote_event_prospect_to_prospect

    prospect, created = promote_event_prospect_to_prospect(row)
    if created:
        log_activity(
            action="prospect_created",
            object_type="prospect",
            object_id=prospect.id,
            description=f"Promoted event prospect #{row.id} ({row.event_name}) to prospect",
            user=request.user,
        )
    return Response({"success": True, "prospect_id": prospect.id, "created": created})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def event_prospect_reject(request: Request, event_prospect_id: int) -> Response:
    try:
        row = _owned_qs(request, EventProspect.objects.all()).get(id=event_prospect_id)
    except EventProspect.DoesNotExist:
        return Response({"success": False, "error": "Event prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    reason = (request.data.get("reason") or "").strip()
    row.status = "irrelevant"
    if reason:
        row.notes = (row.notes + "\n" if row.notes else "") + f"Irrelevant: {reason}"
    row.save(update_fields=["status", "notes", "updated_at"])
    return Response({"success": True})


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def leads_list(request: Request) -> Response:
    if request.method == "POST":
        serializer = LeadWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save(owner=request.user)
        log_activity(
            action="lead_created",
            object_type="lead",
            object_id=lead.id,
            description=f"Manually created lead #{lead.id}",
            user=request.user,
        )
        return Response(
            {"success": True, "data": LeadSerializer(lead).data},
            status=status.HTTP_201_CREATED,
        )

    qs = _owned_qs(request, Lead.objects.all()).order_by("-created_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = _apply_search(qs, request, ["company", "event_name", "email", "website", "full_name"])
    return Response({"success": True, "data": _pagination(request, qs, LeadSerializer)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def leads_bulk_interested(request: Request) -> Response:
    ids = request.data.get("lead_ids") or []
    count = _owned_qs(request, Lead.objects.all()).filter(id__in=ids, status=LeadStatus.CONTACTED).update(status=LeadStatus.INTERESTED)
    return Response({"success": True, "count": count})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def leads_bulk_reject(request: Request) -> Response:
    ids = request.data.get("lead_ids") or []
    count = _owned_qs(request, Lead.objects.all()).filter(id__in=ids, status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED]).update(
        status=LeadStatus.REJECTED, rejected_at=timezone.now()
    )
    return Response({"success": True, "count": count})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def leads_bulk_sync_crm(request: Request) -> Response:
    ids = request.data.get("lead_ids") or []
    if not ids:
        return Response({"success": False, "error": "No lead IDs provided"}, status=status.HTTP_400_BAD_REQUEST)

    from crm_integration.models import PerfexLeadSync
    from crm_integration.tasks import sync_lead_to_perfex

    leads = _owned_qs(request, Lead.objects.all()).filter(id__in=ids, status=LeadStatus.INTERESTED)
    count = 0
    for lead in leads:
        PerfexLeadSync.objects.get_or_create(lead=lead)
        sync_lead_to_perfex.delay(lead.id)
        count += 1
        log_activity(
            action="lead_synced",
            object_type="lead",
            object_id=lead.id,
            description=f"Lead #{lead.id} queued for CRM sync",
            user=request.user,
        )
    return Response({"success": True, "count": count, "message": f"Queued {count} lead(s) for CRM sync"})


@dashboard_api_view(["GET", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_detail(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "PATCH":
        serializer = LeadWriteSerializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            action="lead_updated",
            object_type="lead",
            object_id=lead.id,
            description=f"Updated lead #{lead.id}",
            user=request.user,
        )
        return Response({"success": True, "data": LeadSerializer(lead).data})

    return Response({"success": True, "data": LeadSerializer(lead).data})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_duplicates(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
    rows = find_lead_duplicates(lead, _owned_qs(request, Lead.objects.all()))
    return Response({"success": True, "data": {"items": rows, "total": len(rows)}})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_mark_interested(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
    if lead.status != LeadStatus.CONTACTED:
        return Response({"success": False, "error": "Only CONTACTED leads can be marked interested."}, status=400)
    lead.status = LeadStatus.INTERESTED
    lead.save(update_fields=["status", "updated_at"])
    return Response({"success": True})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_reject(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
    if lead.status in [LeadStatus.REJECTED, LeadStatus.SYNCED]:
        return Response({"success": False, "error": f"Lead already {lead.status}."}, status=400)
    lead.status = LeadStatus.REJECTED
    lead.rejected_at = timezone.now()
    lead.save(update_fields=["status", "rejected_at", "updated_at"])
    return Response({"success": True})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_sync_crm(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
    if lead.status != LeadStatus.INTERESTED:
        return Response({"success": False, "error": "Lead must be INTERESTED before CRM sync."}, status=400)
    from crm_integration.models import PerfexLeadSync
    from crm_integration.tasks import sync_lead_to_perfex

    PerfexLeadSync.objects.get_or_create(lead=lead)
    task = sync_lead_to_perfex.delay(lead.id)
    return Response({"success": True, "task_id": task.id})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def metrics_summary(request: Request) -> Response:
    cache_key = f"dashboard:metrics_summary:{request.user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({"success": True, "data": cached})

    since = timezone.now() - timedelta(days=7)
    targets_qs = _owned_qs(request, ScrapeTarget.objects.all())
    scrape_recent = _owned_qs(request, ScrapeRun.objects.all()).filter(started_at__gte=since)
    crawl_recent = _owned_qs(request, CrawlRun.objects.all()).filter(started_at__gte=since)
    prospects_qs = _owned_qs(request, Prospect.objects.all())
    leads_qs = _owned_qs(request, Lead.objects.all())
    failed_crawls = crawl_recent.filter(status=CrawlRunStatus.FAILED).count()
    data = {
        "targets_enabled": targets_qs.filter(enabled=True).count(),
        "scrape_runs_recent": scrape_recent.count(),
        "scrape_success_recent": scrape_recent.filter(status=ScrapeRunStatus.SUCCESS).count(),
        "crawl_runs_recent": crawl_recent.count(),
        "prospects_new": prospects_qs.filter(status=ProspectStatus.NEW).count(),
        "prospects_contacted": prospects_qs.filter(status=ProspectStatus.CONTACTED).count(),
        "leads_interested": leads_qs.filter(status=LeadStatus.INTERESTED).count(),
        "leads_synced": leads_qs.filter(status=LeadStatus.SYNCED).count(),
        "failed_crawls_recent": failed_crawls,
        "prospect_status_breakdown": list(
            prospects_qs.values("status").annotate(count=Count("id")).order_by("status")
        ),
        "lead_status_breakdown": list(
            leads_qs.values("status").annotate(count=Count("id")).order_by("status")
        ),
    }
    cache.set(cache_key, data, 60)
    return Response({"success": True, "data": data})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def metrics_quality(request: Request) -> Response:
    since = timezone.now() - timedelta(days=7)
    prospects_qs = _owned_qs(request, Prospect.objects.all())
    leads_qs = _owned_qs(request, Lead.objects.all())
    event_qs = _owned_qs(request, EventProspect.objects.all())
    crawl_run_ids = _owned_qs(request, CrawlRun.objects.all()).values_list("id", flat=True)
    crawl_domains = CrawlRunDomainResult.objects.filter(crawl_run_id__in=crawl_run_ids)
    ai_jobs = _owned_qs(request, AISearchJob.objects.filter(updated_at__gte=since))

    quality = build_quality_metrics(
        prospects_qs=prospects_qs,
        leads_qs=leads_qs,
        event_prospects_qs=event_qs,
        crawl_domain_qs=crawl_domains,
        since=since,
    )
    discovery = build_discovery_drop_metrics(
        ai_jobs_qs=ai_jobs,
        crawl_domain_qs=crawl_domains,
        since=since,
    )
    return Response({"success": True, "data": {**quality, "discovery_drops": discovery}})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def notifications_list(request: Request) -> Response:
    limit = _parse_positive_int(
        request.query_params.get("limit"),
        field="limit",
        default=20,
        minimum=1,
        maximum=100,
    )
    rows = Notification.objects.filter(user=request.user).order_by("-created_at")[:limit]
    unread = Notification.objects.filter(user=request.user, read=False).count()
    return Response(
        {
            "success": True,
            "data": {
                "unread_count": unread,
                "items": [
                    {
                        "id": n.id,
                        "type": n.type,
                        "title": n.title,
                        "message": n.message,
                        "read": n.read,
                        "link_url": n.link_url,
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    }
                    for n in rows
                ],
            },
        }
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def notifications_read_all(request: Request) -> Response:
    updated = Notification.objects.filter(user=request.user, read=False).update(
        read=True,
        read_at=timezone.now(),
    )
    return Response({"success": True, "marked": updated})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def notification_mark_read(request: Request, notif_id: int) -> Response:
    try:
        row = Notification.objects.get(id=notif_id, user=request.user)
    except Notification.DoesNotExist:
        return Response({"success": False, "error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)
    row.mark_read()
    return Response({"success": True})


def _ai_search_configured() -> bool:
    gemini = bool((getattr(settings, "GEMINI_API_KEY", None) or "").strip())
    serper = bool(_get_serper_api_key())
    if getattr(settings, "AI_SEARCH_REQUIRE_GEMINI", True):
        return gemini
    return gemini or serper


@dashboard_api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def ai_search_jobs(request: Request) -> Response:
    if request.method == "POST":
        if not _ai_search_configured():
            return Response(
                {
                    "success": False,
                    "error": (
                        "AI search is not configured. Set GEMINI_API_KEY on the server "
                        "(and SERPER_API_KEY for company-first discovery)."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        seed_topic = (request.data.get("seed_topic") or "").strip()
        if not seed_topic:
            return Response(
                {"success": False, "error": "seed_topic is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        industry = (request.data.get("industry") or "").strip()[:200]
        region = (request.data.get("region") or "").strip()[:200]
        job = AISearchJob.objects.create(
            owner=request.user,
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
            description=f"Started AI search job: {job.seed_topic[:80]}",
            user=request.user,
        )
        return Response(
            {"success": True, "data": AISearchJobSerializer(job).data},
            status=status.HTTP_201_CREATED,
        )

    qs = _owned_qs(request, AISearchJob.objects.all()).order_by("-created_at")
    return Response({"success": True, "data": _pagination(request, qs, AISearchJobSerializer)})


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def ai_search_job_detail(request: Request, job_id: int) -> Response:
    try:
        job = _owned_qs(request, AISearchJob.objects.all()).get(pk=job_id)
    except AISearchJob.DoesNotExist:
        return Response({"success": False, "error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    res_qs = job.results.all().order_by("-created_at", "-id")
    return Response(
        {
            "success": True,
            "data": {
                "job": AISearchJobSerializer(job).data,
                "results": _pagination(request, res_qs, AISearchResultSerializer),
            },
        }
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def ai_search_result_promote(request: Request, result_id: int) -> Response:
    try:
        result = AISearchResult.objects.select_related("job").get(pk=result_id)
    except AISearchResult.DoesNotExist:
        return Response({"success": False, "error": "Result not found"}, status=status.HTTP_404_NOT_FOUND)

    if not _owned_qs(request, AISearchJob.objects.filter(pk=result.job_id)).exists():
        return Response({"success": False, "error": "Result not found"}, status=status.HTTP_404_NOT_FOUND)

    from crawler.services.ai_page_extract import result_promotable

    if not result_promotable(result):
        return Response(
            {
                "success": False,
                "error": (
                    "This result does not meet the minimum lead score for promotion. "
                    "Run a new search or wait for crawl analysis."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    prospect, created = promote_ai_search_result_to_prospect(
        result,
        owner_id=request.user.id,
    )
    result.refresh_from_db()
    if created:
        log_activity(
            action="prospect_created",
            object_type="prospect",
            object_id=prospect.id,
            description=f"Promoted AI search result #{result.id} ({result.domain}) to prospect",
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

