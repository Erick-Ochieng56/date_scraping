from __future__ import annotations

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle


class DashboardUserRateThrottle(UserRateThrottle):
    """Rate limit for dashboard SPA API endpoints (per authenticated user)."""

    scope = "dashboard"


def dashboard_api_view(methods):
    """Apply dashboard throttling then @api_view (DRF policy-before-api_view order)."""

    def decorator(view_func):
        view_func = throttle_classes([DashboardUserRateThrottle])(view_func)
        return api_view(methods)(view_func)

    return decorator
