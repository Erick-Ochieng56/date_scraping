from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """
    JSON API under /dashboard/api/ backs the React SPA (session auth), for both
    the staff and admin roles. There is no server-rendered template UI here.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    verbose_name = 'Dashboard (React SPA API)'
