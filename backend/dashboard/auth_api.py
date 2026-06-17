from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from dashboard.permissions import scraper_group_name


@require_POST
def api_auth_login(request: HttpRequest) -> JsonResponse:
    """Session login for SPA users (staff and admin)."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username:
        return JsonResponse(
            {"success": False, "error": "Username is required."}, status=400
        )

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse(
            {"success": False, "error": "Invalid username or password."}, status=400
        )

    gname = scraper_group_name()
    is_admin = bool(user.is_staff)
    is_staff_portal = user.groups.filter(name=gname).exists()
    if not is_admin and not is_staff_portal:
        return JsonResponse(
            {
                "success": False,
                "error": "Your account is not enabled for the staff dashboard.",
            },
            status=403,
        )

    login(request, user)
    return JsonResponse(
        {
            "success": True,
            "user": {"username": user.get_username(), "role": "admin" if is_admin else "staff"},
        }
    )


@require_POST
def api_auth_logout(request: HttpRequest) -> JsonResponse:
    # Idempotent logout: if the session is already anonymous/expired, still return success.
    if request.user.is_authenticated:
        logout(request)
    return JsonResponse({"success": True})


@ensure_csrf_cookie
@require_GET
def api_auth_me(request: HttpRequest) -> JsonResponse:
    """Return session + role for the SPA; sets CSRF cookie when needed."""
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})

    if request.user.is_staff:
        return JsonResponse(
            {
                "authenticated": True,
                "role": "admin",
                "username": request.user.get_username(),
            }
        )

    if request.user.groups.filter(name=scraper_group_name()).exists():
        return JsonResponse(
            {
                "authenticated": True,
                "role": "staff",
                "username": request.user.get_username(),
            }
        )

    # Stale session (e.g. Django admin user without portal group) — clear so API calls get 401, not 403.
    logout(request)
    return JsonResponse(
        {
            "authenticated": False,
            "reason": "no_portal_access",
        }
    )
