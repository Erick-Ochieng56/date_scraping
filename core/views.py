from __future__ import annotations

import json
import os

from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST


def _ops_authorized(request: HttpRequest) -> bool:
    token = os.getenv("OPS_TOKEN", "") or ""
    if not token:
        return False
    return request.headers.get("X-OPS-TOKEN", "") == token


@require_GET
def home(_: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "message": "Leads App API",
        "endpoints": {
            "health": "/healthz",
            "readiness": "/readyz",
            "admin": "/admin/",
        }
    })


@require_GET
def healthz(_: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(_: HttpRequest) -> JsonResponse:
    details: dict[str, object] = {"time": timezone.now().isoformat()}

    # DB check
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        details["db"] = "ok"
    except Exception as exc:
        details["db"] = f"error: {exc}"
        return JsonResponse({"status": "error", "details": details}, status=503)

    # Redis check (optional)
    redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or ""
    if redis_url:
        try:
            import redis

            r = redis.Redis.from_url(redis_url)
            r.ping()
            details["redis"] = "ok"
        except Exception as exc:
            details["redis"] = f"error: {exc}"
            return JsonResponse({"status": "error", "details": details}, status=503)
    else:
        details["redis"] = "skipped"

    return JsonResponse({"status": "ok", "details": details})


@require_POST
def trigger_scrape(request: HttpRequest) -> JsonResponse:
    if not _ops_authorized(request):
        return JsonResponse({"detail": "unauthorized"}, status=401)

    from scraper.tasks import enqueue_enabled_targets, scrape_target

    body = {}
    if request.body:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}

    target_id = body.get("target_id")
    if target_id:
        scrape_target.delay(target_id=int(target_id), trigger="manual")
        return JsonResponse({"enqueued": 1, "target_id": int(target_id)})

    count = enqueue_enabled_targets.delay()
    return JsonResponse({"enqueued": "all", "task": count.id})


@require_POST
def trigger_sync(request: HttpRequest) -> JsonResponse:
    if not _ops_authorized(request):
        return JsonResponse({"detail": "unauthorized"}, status=401)

    from crm_integration.tasks import sync_lead_to_perfex, sync_pending_to_perfex

    body = {}
    if request.body:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}

    lead_id = body.get("lead_id")
    if lead_id:
        sync_lead_to_perfex.delay(lead_id=int(lead_id))
        return JsonResponse({"enqueued": 1, "lead_id": int(lead_id)})

    task = sync_pending_to_perfex.delay()
    return JsonResponse({"enqueued": "pending", "task": task.id})
