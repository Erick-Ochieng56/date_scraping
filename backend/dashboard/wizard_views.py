from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from dashboard.permissions import staff_json_api_user
from dashboard.utils import log_activity
from scraper.models import ScrapeTarget, ScrapeTargetType
from scraper.services.auto_discover import auto_create_target, detect_platform_type
from scraper.services.url_safety import check_public_url


def _target_type_value(raw) -> str:
    if raw is None:
        return ScrapeTargetType.HTML
    if isinstance(raw, ScrapeTargetType):
        return raw
    s = str(raw).strip().lower()
    if s in ScrapeTargetType.values:
        return s
    return ScrapeTargetType.HTML


@require_GET
@staff_json_api_user
def wizard_detect_platform(request: HttpRequest) -> JsonResponse:
    """Detect listing platform from URL and return suggested scrape target config."""
    url = (request.GET.get("url") or "").strip()
    if not url:
        return JsonResponse({"success": False, "error": "URL parameter required"}, status=400)

    platform = detect_platform_type(url)
    auto = auto_create_target(url)
    target_type = _target_type_value(auto.get("target_type"))

    return JsonResponse(
        {
            "success": True,
            "platform": platform or "generic",
            "detected": platform is not None,
            "suggested_config": {
                "name": auto.get("name"),
                "target_type": target_type,
                "start_url": url,
                "run_every_minutes": auto.get("run_every_minutes", 120),
                "enabled": auto.get("enabled", True),
                "config": auto.get("config") or {},
            },
        }
    )


@require_POST
@staff_json_api_user
def wizard_create_target(request: HttpRequest) -> JsonResponse:
    """Create a scrape target using auto-detected platform config plus optional overrides."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    url = (body.get("url") or "").strip()
    name = (body.get("name") or "").strip() or None
    config_overrides = body.get("config") or {}

    if not url:
        return JsonResponse({"success": False, "error": "URL is required"}, status=400)
    if config_overrides is not None and not isinstance(config_overrides, dict):
        return JsonResponse({"success": False, "error": "config must be a JSON object"}, status=400)

    url_ok, url_reason = check_public_url(url)
    if not url_ok:
        return JsonResponse({"success": False, "error": url_reason}, status=400)

    auto_config = auto_create_target(url, name)
    final_config = dict(auto_config.get("config") or {})
    if isinstance(config_overrides, dict):
        final_config.update(config_overrides)

    target_name = name or auto_config["name"]
    existing = ScrapeTarget.objects.filter(name=target_name).first()
    if existing:
        return JsonResponse(
            {
                "success": False,
                "error": f"Target with name '{target_name}' already exists",
                "target_id": existing.id,
                "existing": True,
            },
            status=409,
        )

    target_type = _target_type_value(body.get("target_type") or auto_config.get("target_type"))
    run_every = body.get("run_every_minutes", auto_config.get("run_every_minutes", 120))
    try:
        run_every = max(1, int(run_every))
    except (TypeError, ValueError):
        run_every = 120

    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        enabled = str(enabled).lower() in {"1", "true", "yes"}

    target = ScrapeTarget.objects.create(
        name=target_name,
        start_url=url,
        enabled=enabled,
        target_type=target_type,
        run_every_minutes=run_every,
        config=final_config,
        owner=request.user,
    )
    log_activity(
        action="target_created",
        object_type="target",
        object_id=target.id,
        description=f"Target «{target.name}» created via wizard",
        user=request.user,
    )
    platform = detect_platform_type(url)

    return JsonResponse(
        {
            "success": True,
            "target_id": target.id,
            "name": target.name,
            "platform": platform or "generic",
            "message": "Target created successfully",
        },
        status=201,
    )
