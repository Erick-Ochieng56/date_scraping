from django.urls import path

from dashboard.api import admin_views

urlpatterns = [
    path("users/", admin_views.users_list, name="admin_v1_users_list"),
    path("users/create-staff/", admin_views.users_create_staff, name="admin_v1_users_create_staff"),
    path("users/<int:user_id>/", admin_views.users_update, name="admin_v1_users_update"),
    path("ownership/transfer/", admin_views.ownership_transfer, name="admin_v1_ownership_transfer"),
    path("scraper/targets/", admin_views.scraper_targets_list, name="admin_v1_scraper_targets_list"),
    path("scraper/targets/<int:target_id>/trigger/", admin_views.scraper_target_trigger, name="admin_v1_scraper_target_trigger"),
    path("scraper/runs/", admin_views.scraper_runs_list, name="admin_v1_scraper_runs_list"),
    path("scraper/runs/<int:run_id>/retry/", admin_views.scraper_run_retry, name="admin_v1_scraper_run_retry"),
    path("crawler/sources/", admin_views.crawler_sources_list, name="admin_v1_crawler_sources_list"),
    path("crawler/sources/<int:source_id>/", admin_views.crawler_source_update, name="admin_v1_crawler_source_update"),
    path("crawler/domains/", admin_views.crawler_domains_list, name="admin_v1_crawler_domains_list"),
    path("crawler/domains/<int:domain_id>/trigger/", admin_views.crawler_domain_trigger, name="admin_v1_crawler_domain_trigger"),
    path("crawler/domains/reset-failed/", admin_views.crawler_domains_reset_failed, name="admin_v1_crawler_domains_reset_failed"),
    path("crawler/runs/", admin_views.crawler_runs_list, name="admin_v1_crawler_runs_list"),
    path("crawler/runs/<int:run_id>/cancel/", admin_views.crawler_run_cancel, name="admin_v1_crawler_run_cancel"),
    path("crawler/runs/cancel-all/", admin_views.crawler_runs_cancel_all, name="admin_v1_crawler_runs_cancel_all"),
    path("ai-search/jobs/<int:job_id>/", admin_views.admin_ai_search_job_detail, name="admin_v1_ai_search_job_detail"),
    path("ai-search/jobs/", admin_views.admin_ai_search_jobs, name="admin_v1_ai_search_jobs"),
]
