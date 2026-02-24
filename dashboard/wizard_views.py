from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from dashboard.utils import log_activity
from scraper.models import ScrapeTarget
from scraper.services.auto_discover import auto_create_target, detect_platform_type


@login_required
@require_GET
def wizard_detect_platform(request: HttpRequest) -> JsonResponse:
    """API endpoint to detect platform from URL."""
    url = request.GET.get('url')
    if not url:
        return JsonResponse({"error": "URL parameter required"}, status=400)
    
    platform = detect_platform_type(url)
    config = auto_create_target(url)
    
    return JsonResponse({
        "platform": platform or "generic",
        "detected": platform is not None,
        "suggested_config": {
            "name": config.get("name"),
            "target_type": config.get("target_type"),
            "config": config.get("config"),
        }
    })


@login_required
@require_POST
def wizard_create_target(request: HttpRequest) -> JsonResponse:
    """API endpoint to create target from wizard."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        url = body.get("url")
        name = body.get("name")
        config_overrides = body.get("config", {})
        
        if not url:
            return JsonResponse({"error": "URL is required"}, status=400)
        
        # Auto-detect and generate base config
        auto_config = auto_create_target(url, name)
        
        # Merge any user overrides
        final_config = auto_config["config"].copy()
        final_config.update(config_overrides)
        
        # Check if target with this name already exists
        target_name = name or auto_config["name"]
        existing = ScrapeTarget.objects.filter(name=target_name).first()
        if existing:
            return JsonResponse({
                "error": f"Target with name '{target_name}' already exists",
                "target_id": existing.id,
                "existing": True
            }, status=409)
        
        # Create the target
        target = ScrapeTarget.objects.create(
            name=target_name,
            start_url=url,
            enabled=body.get("enabled", True),
            target_type=auto_config["target_type"],
            run_every_minutes=body.get("run_every_minutes", 120),
            config=final_config,
        )
        log_activity(
            action="target_created",
            object_type="target",
            object_id=target.id,
            description=f"Target «{target.name}» created via wizard",
            user=request.user,
        )
        platform = detect_platform_type(url)
        
        return JsonResponse({
            "success": True,
            "target_id": target.id,
            "name": target.name,
            "platform": platform or "generic",
            "message": f"Target created successfully"
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

