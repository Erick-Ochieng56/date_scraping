from django.urls import include, path

from . import auth_api, export_views, wizard_views

app_name = 'dashboard'

urlpatterns = [
    # Auth (Scraper portal + CSRF priming)
    path('api/auth/login/', auth_api.api_auth_login, name='api_auth_login'),
    path('api/auth/logout/', auth_api.api_auth_logout, name='api_auth_logout'),
    path('api/auth/me/', auth_api.api_auth_me, name='api_auth_me'),

    # Export endpoints
    path('export/prospects/csv/', export_views.export_prospects_csv, name='export_prospects_csv'),
    path('export/leads/csv/', export_views.export_leads_csv, name='export_leads_csv'),

    # Wizard endpoints
    path('wizard/detect-platform/', wizard_views.wizard_detect_platform, name='wizard_detect_platform'),
    path('wizard/create-target/', wizard_views.wizard_create_target, name='wizard_create_target'),

    path("api/v1/", include("dashboard.api.urls")),
    path("api/admin/v1/", include("dashboard.api.admin_urls")),
]

