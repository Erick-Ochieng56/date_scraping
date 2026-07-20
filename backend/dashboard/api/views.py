from __future__ import annotations

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
    CrawlSource,
    DiscoveredDomain,
)
from crawler.discovery import (
    _get_serper_api_key,
    discover_websites,
    discovery_hits_from_user_payload,
    save_discovered_domains,
)
from crawler.services.discovery_qualify import filter_discovery_hits
from crawler.services.promote_ai_result import promote_ai_search_result_to_prospect
from crawler.tasks import crawl_domain_task, discover_websites_task, run_ai_search_job
from dashboard.api.decorators import dashboard_api_view
from dashboard.api.permissions import IsDashboardPortalUser
from dashboard.api.serializers import (
    AISearchJobSerializer,
    AISearchResultSerializer,
    CrawlSourceSerializer,
    CrawlRunDomainResultSerializer,
    DiscoveredDomainSerializer,
    CrawlRunSerializer,
    LeadSerializer,
    ProspectSerializer,
    ScrapeRunSerializer,
    ScrapeTargetSerializer,
)
from dashboard.utils import log_activity
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.tasks import try_start_scrape


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
    return Response(
        {
            "success": False,
            "error": "Scraper runs are manual per target. Use /targets/<id>/trigger/ for individual domains.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def trigger_target(request: Request, target_id: int) -> Response:
    try:
        target = _owned_qs(request, ScrapeTarget.objects.all()).get(id=target_id)
    except ScrapeTarget.DoesNotExist:
        return Response({"success": False, "error": "Target not found"}, status=status.HTTP_404_NOT_FOUND)
    run, task = try_start_scrape(target, trigger="manual", initiated_by_id=request.user.id)
    if run is None:
        return Response(
            {"success": False, "error": "A scrape is already in progress for this target."},
            status=status.HTTP_409_CONFLICT,
        )
    log_activity(
        action="scrape_triggered",
        object_type="target",
        object_id=target.id,
        description=f"Scrape triggered for {target.name}",
        user=request.user,
        metadata={"task_id": task.id},
    )
    return Response({"success": True, "message": f"Scrape triggered for {target.name}", "task_id": task.id})


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
    new_run, task = try_start_scrape(run.target, trigger="manual", initiated_by_id=request.user.id)
    if new_run is None:
        return Response(
            {"success": False, "error": "A scrape is already in progress for this target."},
            status=status.HTTP_409_CONFLICT,
        )
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
    qs = CrawlRunDomainResult.objects.select_related("domain").filter(crawl_run_id=run_id).order_by("-updated_at")
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


_DISCOVER_MAX_RESULTS_CAP = 20


def _parse_discover_max_results(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DISCOVER_MAX_RESULTS_CAP
    return max(1, min(_DISCOVER_MAX_RESULTS_CAP, value))


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawler_discover_preview(request: Request) -> Response:
    """
    Ad-hoc SERP discovery preview for the frontend Discover page: run the query,
    qualify each hit with the same rules the scheduled pipeline uses, and return
    both kept and dropped hits (with drop reasons) without persisting anything.

    The frontend's entire Discover workflow (CrawlerDiscoverPage) shipped wired
    to this endpoint and the queue one below, but neither existed — every
    Preview/Queue action 404'd.
    """
    query = (request.data.get("query") or "").strip()
    if not query:
        return Response(
            {"success": False, "error": "query is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    max_results = _parse_discover_max_results(request.data.get("max_results"))

    hits = discover_websites(query, max_results=max_results)
    kept, dropped = filter_discovery_hits(hits)

    return Response(
        {
            "success": True,
            "hits": kept,
            "urls": [h.get("source_url") or h.get("domain") for h in kept],
            "dropped": dropped,
            "dropped_count": len(dropped),
        }
    )


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def crawler_discover_queue(request: Request) -> Response:
    """
    Persist the Discover page's selection as DiscoveredDomain rows (owned by the
    requesting user) and optionally start a crawl run over them immediately.

    When `urls` is provided (the normal path — the user curated the preview
    list), those exact landing URLs are queued without re-running the search.
    Otherwise the query is re-run and re-qualified server-side.
    """
    query = (request.data.get("query") or "").strip()
    raw_urls = request.data.get("urls") or []
    auto_crawl = bool(request.data.get("auto_crawl"))

    if not isinstance(raw_urls, list):
        return Response(
            {"success": False, "error": "urls must be a list."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if raw_urls:
        hits = discovery_hits_from_user_payload(raw_urls)
    elif query:
        max_results = _parse_discover_max_results(request.data.get("max_results"))
        found = discover_websites(query, max_results=max_results)
        hits, _dropped = filter_discovery_hits(found)
    else:
        return Response(
            {"success": False, "error": "Provide urls or a query."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not hits:
        return Response(
            {"success": True, "queued": 0, "new_domains": 0, "run_id": None, "domain_ids": []}
        )

    new_domains = save_discovered_domains(hits, source=None, owner_id=request.user.id)

    domain_bases = [h["domain"] for h in hits]
    domain_ids = list(
        DiscoveredDomain.objects.filter(domain__in=domain_bases).values_list("id", flat=True)
    )

    run_id: int | None = None
    if auto_crawl:
        pending_ids = list(
            DiscoveredDomain.objects.filter(
                id__in=domain_ids, crawl_status="pending"
            ).values_list("id", flat=True)
        )
        if pending_ids:
            run = CrawlRun.objects.create(
                owner=request.user,
                trigger=CrawlRunTrigger.MANUAL,
                status=CrawlRunStatus.RUNNING,
                started_at=timezone.now(),
                # Persisted before any enqueue — _finalize_crawl_run_if_complete
                # compares completed-domain count against this field.
                domains_queued=len(pending_ids),
            )
            for domain_id in pending_ids:
                CrawlRunDomainResult.objects.get_or_create(
                    crawl_run_id=run.id,
                    domain_id=domain_id,
                    defaults={"state": "queued"},
                )
                crawl_domain_task.delay(
                    domain_id=domain_id, run_id=run.id, owner_id=request.user.id
                )
            run_id = run.id

    log_activity(
        action="crawl_triggered",
        object_type="crawl_run" if run_id else "crawl_domain",
        object_id=run_id or (domain_ids[0] if domain_ids else 0),
        description=f"Discover queue: {len(hits)} domain(s), {new_domains} new"
        + (f", crawl run #{run_id}" if run_id else ""),
        user=request.user,
        metadata={"queued": len(hits), "new_domains": new_domains, "run_id": run_id},
    )

    return Response(
        {
            "success": True,
            "queued": len(hits),
            "new_domains": new_domains,
            "run_id": run_id,
            "domain_ids": domain_ids,
        }
    )


def _apply_search(qs, request: Request, fields: list[str]):
    search = (request.query_params.get("search") or "").strip()
    if not search:
        return qs
    q = Q()
    for field in fields:
        q |= Q(**{f"{field}__icontains": search})
    return qs.filter(q)


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospects_list(request: Request) -> Response:
    qs = _owned_qs(request, Prospect.objects.all()).order_by("-created_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = _apply_search(qs, request, ["company", "event_name", "email", "website"])
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


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def prospect_detail(request: Request, prospect_id: int) -> Response:
    try:
        prospect = _owned_qs(request, Prospect.objects.all()).get(id=prospect_id)
    except Prospect.DoesNotExist:
        return Response({"success": False, "error": "Prospect not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True, "data": ProspectSerializer(prospect).data})


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


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def leads_list(request: Request) -> Response:
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


@dashboard_api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def lead_detail(request: Request, lead_id: int) -> Response:
    try:
        lead = _owned_qs(request, Lead.objects.all()).get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"success": False, "error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True, "data": LeadSerializer(lead).data})


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


def _ai_search_configured() -> bool:
    gemini = bool((getattr(settings, "GEMINI_API_KEY", None) or "").strip())
    serper = bool(_get_serper_api_key())
    if getattr(settings, "AI_SEARCH_REQUIRE_GEMINI", True):
        return gemini
    return gemini or serper


AI_SEARCH_NON_TERMINAL_STATUSES = ("pending", "generating", "searching")


def _ai_search_rate_limit_error(owner) -> str | None:
    """
    Return an error message if `owner` shouldn't be allowed to start a new AI
    search job right now, else None.

    The only prior throttle on job creation was a generic 120/min per-user
    request rate limiter (DashboardUserRateThrottle) — no cap on concurrent
    jobs or total jobs per day, despite a single job triggering on the order
    of 40+ real Gemini/Serper API calls (query generation + grounded search +
    up to 12x3 extraction retries). A user could queue many jobs back-to-back,
    each burning real API spend, limited only by that generic per-minute
    request throttle.
    """
    max_concurrent = int(getattr(settings, "AI_SEARCH_MAX_CONCURRENT_JOBS_PER_USER", 1) or 1)
    in_progress = AISearchJob.objects.filter(
        owner=owner, status__in=AI_SEARCH_NON_TERMINAL_STATUSES
    ).count()
    if in_progress >= max_concurrent:
        return (
            f"{owner.get_username()} already has {in_progress} AI search job(s) in "
            "progress. Wait for it to finish before starting another."
        )

    max_per_day = int(getattr(settings, "AI_SEARCH_MAX_JOBS_PER_DAY_PER_USER", 20) or 20)
    since = timezone.now() - timedelta(hours=24)
    jobs_today = AISearchJob.objects.filter(owner=owner, created_at__gte=since).count()
    if jobs_today >= max_per_day:
        return (
            f"{owner.get_username()} has reached the daily limit of {max_per_day} AI "
            "search jobs. Try again later."
        )

    return None


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
        rate_limit_error = _ai_search_rate_limit_error(request.user)
        if rate_limit_error:
            return Response(
                {"success": False, "error": rate_limit_error},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
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

