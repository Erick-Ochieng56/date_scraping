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
            "ops": {
                "trigger_scrape": "/ops/trigger-scrape",
                "trigger_sync": "/ops/trigger-sync",
                "auto_create_target": "/ops/auto-create-target",
            }
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


@require_POST
def auto_create_target(request: HttpRequest) -> JsonResponse:
    """
    Auto-create a scrape target from a URL using intelligent platform detection.
    
    Requires OPS_TOKEN authentication.
    Body: {"url": "...", "name": "..." (optional)}
    """
    if not _ops_authorized(request):
        return JsonResponse({"detail": "unauthorized"}, status=401)
    
    try:
        body = {}
        if request.body:
            try:
                body = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        url = body.get("url")
        if not url:
            return JsonResponse({"error": "url is required"}, status=400)
        
        # Validate URL format
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return JsonResponse({"error": "Invalid URL format"}, status=400)
        
        # Auto-discover platform and generate config
        from scraper.services.auto_discover import (
            auto_create_target as auto_create,
            detect_platform_type,
        )
        from scraper.models import ScrapeTarget
        
        name = body.get("name")
        target_config = auto_create(url, name)
        
        # Check if target with this name already exists
        existing = ScrapeTarget.objects.filter(name=target_config["name"]).first()
        if existing:
            return JsonResponse({
                "error": f"Target with name '{target_config['name']}' already exists",
                "target_id": existing.id,
                "existing": True
            }, status=409)
        
        # Create the target
        target = ScrapeTarget.objects.create(
            name=target_config["name"],
            start_url=target_config["start_url"],
            enabled=target_config["enabled"],
            target_type=target_config["target_type"],
            run_every_minutes=target_config["run_every_minutes"],
            config=target_config["config"],
        )
        
        platform = detect_platform_type(url)
        
        return JsonResponse({
            "created": True,
            "target_id": target.id,
            "name": target.name,
            "platform": platform,
            "target_type": target.target_type,
            "message": f"Target created successfully. Platform: {platform or 'unknown (generic config)'}"
        }, status=201)
        
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Failed to auto-create target")
        return JsonResponse({"error": str(exc)}, status=500)
