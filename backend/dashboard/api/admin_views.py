from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from dashboard.api.permissions import IsDashboardAdminUser
from dashboard.api.serializers import AISearchJobSerializer, AISearchResultSerializer
from dashboard.permissions import scraper_group_name
from dashboard.utils import log_activity
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.tasks import scrape_target
from crawler.models import AISearchJob, CrawlRun, CrawlRunStatus, CrawlRunTrigger, CrawlSource, DiscoveredDomain
from crawler.tasks import crawl_domain_task, run_ai_search_job
from leads.models import Lead, Prospect
from celery import current_app
from django.utils import timezone

User = get_user_model()


def _pagination(request: Request, rows: list[dict]):
    page = max(1, int(request.query_params.get("page", "1")))
    page_size = min(100, max(1, int(request.query_params.get("page_size", "25"))))
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


@api_view(["GET"])
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


@api_view(["POST"])
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


@api_view(["PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def users_update(request: Request, user_id: int) -> Response:
    before = {
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"success": False, "error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    gname = scraper_group_name()
    scraper_group, _ = Group.objects.get_or_create(name=gname)

    role = request.data.get("role")
    is_active = request.data.get("is_active")

    if is_active is not None:
        if user.id == request.user.id and is_active is False:
            return Response(
                {"success": False, "error": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = bool(is_active)

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


@api_view(["POST"])
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


@api_view(["GET"])
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


@api_view(["POST"])
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


@api_view(["GET"])
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


@api_view(["POST"])
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
    return {
        "id": run.id,
        "trigger": run.trigger,
        "status": run.status,
        "status_display": run.get_status_display(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "task_id": run.task_id,
        "error_text": run.error_text,
        "domains_queued": run.domains_queued,
        "prospects_created": run.prospects_created,
        "prospects_updated": run.prospects_updated,
        "owner_id": run.owner_id,
    }


@api_view(["GET"])
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


@api_view(["PATCH"])
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


@api_view(["GET"])
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


@api_view(["POST"])
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


@api_view(["POST"])
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


@api_view(["GET"])
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


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_run_cancel(request: Request, run_id: int) -> Response:
    try:
        run = CrawlRun.objects.get(id=run_id)
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


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def crawler_runs_cancel_all(request: Request) -> Response:
    running = list(CrawlRun.objects.filter(status=CrawlRunStatus.RUNNING))
    cancelled = 0
    for run in running:
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
    page = max(1, int(request.query_params.get("page", "1")))
    page_size = min(100, max(1, int(request.query_params.get("page_size", "25"))))
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


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardAdminUser])
def admin_ai_search_jobs(request: Request) -> Response:
    if request.method == "POST":
        if not (getattr(settings, "GEMINI_API_KEY", None) or "").strip():
            return Response(
                {"success": False, "error": "Gemini API is not configured on the server (GEMINI_API_KEY)."},
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


@api_view(["GET"])
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
