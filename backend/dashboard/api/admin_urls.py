from django.urls import path

from dashboard.api import admin_views

urlpatterns = [
    path("activity/", admin_views.activity_list, name="admin_v1_activity_list"),
    path("settings/status/", admin_views.settings_status, name="admin_v1_settings_status"),
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
    path("scrape-sessions/active/", admin_views.scraper_sessions_active, name="admin_v1_scrape_sessions_active"),
    path("scrape-sessions/<int:session_id>/stop/", admin_views.scraper_session_stop, name="admin_v1_scrape_session_stop"),
    path("crawl-sessions/active/", admin_views.crawler_sessions_active, name="admin_v1_crawl_sessions_active"),
    path("crawl-sessions/<int:run_id>/stop/", admin_views.crawler_session_stop, name="admin_v1_crawl_session_stop"),
    path("crawl-schedules/", admin_views.crawler_schedules_list, name="admin_v1_crawl_schedules_list"),
    path("crawl-schedules/<int:schedule_id>/", admin_views.crawler_schedule_detail, name="admin_v1_crawl_schedule_detail"),
    path("ai-search/jobs/<int:job_id>/", admin_views.admin_ai_search_job_detail, name="admin_v1_ai_search_job_detail"),
    path("ai-search/jobs/", admin_views.admin_ai_search_jobs, name="admin_v1_ai_search_jobs"),
    path(
        "ai-search/results/<int:result_id>/promote/",
        admin_views.admin_ai_search_result_promote,
        name="admin_v1_ai_search_result_promote",
    ),
]
