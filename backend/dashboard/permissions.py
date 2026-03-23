"""
Role helpers for the dashboard API and staff-only HTML views.

- **Staff** (`is_staff`): full Django dashboard + admin-style management; uses the
  template dashboard, not the React Scraper portal login.
- **Scraper**: users in the `scraper` Django group (non-staff). Session login via
  `/dashboard/api/auth/login/` for the SPA; operational APIs and data only.
"""
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
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


class StaffDashboardMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Management pages: staff only (403 for scraper operators)."""

    raise_exception = True

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff)
