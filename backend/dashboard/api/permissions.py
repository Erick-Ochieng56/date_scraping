from __future__ import annotations

from rest_framework.permissions import BasePermission

from dashboard.permissions import user_has_dashboard_api_access


class IsDashboardPortalUser(BasePermission):
    """
    Allow dashboard admins and staff portal users.
    """

    def has_permission(self, request, view) -> bool:
        return bool(user_has_dashboard_api_access(request.user))


class IsDashboardAdminUser(BasePermission):
    """
    Allow only dashboard administrators (Django staff).
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)

