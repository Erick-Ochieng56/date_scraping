from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """
    Template views under /dashboard/ are the staff **admin dashboard**.
    JSON under /dashboard/api/ is shared with the React **scraper dashboard** (session auth).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    verbose_name = 'Dashboard (admin templates + shared API)'
