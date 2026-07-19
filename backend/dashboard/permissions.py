"""
Role helpers for the dashboard API and HTML views.

- **Admin** (`is_staff`, usually superuser): template dashboard + Django admin;
  not the React app session login.
- **Staff** (React): users in the portal Django group (``SCRAPER_GROUP_NAME`` /
  default ``scraper``) who are *not* ``is_staff``. Session login via
  ``/dashboard/api/auth/login/`` for the SPA.
"""
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import HttpRequest, JsonResponse


def scraper_group_name() -> str:
    return getattr(settings, "SCRAPER_GROUP_NAME", "scraper")


def user_has_dashboard_api_access(user) -> bool:
    """Staff or members of the scraper group may call operational JSON APIs."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name=scraper_group_name()).exists()


def dashboard_api_user(view_func):
    """
    JSON API guard: 401 if anonymous, 403 if authenticated but not staff/scraper group.
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "error": "Authentication required"},
                status=401,
            )
        if not user_has_dashboard_api_access(request.user):
            return JsonResponse(
                {
                    "success": False,
                    "error": "You do not have permission to use this API.",
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def staff_json_api_user(view_func):
    """Wizard and other management JSON endpoints — staff only."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "error": "Authentication required"},
                status=401,
            )
        if not request.user.is_staff:
            return JsonResponse(
                {
                    "success": False,
                    "error": "This action is restricted to staff administrators.",
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def any_authenticated_json(view_func):
    """Allow any logged-in user (e.g. logout)."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "error": "Not authenticated"},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped
