from django.urls import path

from dashboard.api import stream_views, views


urlpatterns = [
    path("targets/trigger/", views.trigger_all_targets, name="v1_targets_trigger_all"),
    path("targets/<int:target_id>/trigger/", views.trigger_target, name="v1_target_trigger"),
    path("targets/<int:target_id>/", views.target_detail, name="v1_target_detail"),
    path("targets/", views.targets_list, name="v1_targets_list"),
    path("scrape-runs/", views.scrape_runs_list, name="v1_scrape_runs_list"),
    path("scrape-runs/<int:run_id>/", views.scrape_run_detail, name="v1_scrape_run_detail"),
    path("scrape-runs/<int:run_id>/retry/", views.scrape_run_retry, name="v1_scrape_run_retry"),
    path("crawl-runs/", views.crawl_runs_list, name="v1_crawl_runs_list"),
    path("crawl-runs/trigger/", views.crawl_trigger, name="v1_crawl_trigger"),
    path("crawl-runs/cancel-all/", views.crawl_runs_cancel_all, name="v1_crawl_runs_cancel_all"),
    path("crawl-runs/<int:run_id>/", views.crawl_run_detail, name="v1_crawl_run_detail"),
    path("crawl-runs/<int:run_id>/cancel/", views.crawl_run_cancel, name="v1_crawl_run_cancel"),
    path("crawl-runs/<int:run_id>/domains/", views.crawl_run_domain_results, name="v1_crawl_run_domain_results"),
    path("crawl-sources/", views.crawl_sources_list, name="v1_crawl_sources_list"),
    path("crawl-domains/", views.crawl_domains_list, name="v1_crawl_domains_list"),
    path("crawl-domains/<int:domain_id>/trigger/", views.crawl_domain_trigger, name="v1_crawl_domain_trigger"),
    path("ai-search/jobs/<int:job_id>/", views.ai_search_job_detail, name="v1_ai_search_job_detail"),
    path("ai-search/jobs/", views.ai_search_jobs, name="v1_ai_search_jobs"),
    path(
        "ai-search/results/<int:result_id>/promote/",
        views.ai_search_result_promote,
        name="v1_ai_search_result_promote",
    ),
    path("prospects/", views.prospects_list, name="v1_prospects_list"),
    path("prospects/<int:prospect_id>/", views.prospect_detail, name="v1_prospect_detail"),
    path("prospects/<int:prospect_id>/mark-contacted/", views.prospect_mark_contacted, name="v1_prospect_mark_contacted"),
    path("prospects/<int:prospect_id>/convert/", views.prospect_convert, name="v1_prospect_convert"),
    path("prospects/<int:prospect_id>/reject/", views.prospect_reject, name="v1_prospect_reject"),
    path("prospects/bulk/contacted/", views.prospects_bulk_contacted, name="v1_prospects_bulk_contacted"),
    path("prospects/bulk/convert/", views.prospects_bulk_convert, name="v1_prospects_bulk_convert"),
    path("prospects/bulk/reject/", views.prospects_bulk_reject, name="v1_prospects_bulk_reject"),
    path("leads/", views.leads_list, name="v1_leads_list"),
    path("leads/<int:lead_id>/", views.lead_detail, name="v1_lead_detail"),
    path("leads/<int:lead_id>/mark-interested/", views.lead_mark_interested, name="v1_lead_mark_interested"),
    path("leads/<int:lead_id>/reject/", views.lead_reject, name="v1_lead_reject"),
    path("leads/<int:lead_id>/sync-crm/", views.lead_sync_crm, name="v1_lead_sync_crm"),
    path("leads/bulk/interested/", views.leads_bulk_interested, name="v1_leads_bulk_interested"),
    path("leads/bulk/reject/", views.leads_bulk_reject, name="v1_leads_bulk_reject"),
    path("metrics/summary/", views.metrics_summary, name="v1_metrics_summary"),
    path("stream/runs/", stream_views.stream_runs, name="v1_stream_runs"),
    path("stream/runs/<int:run_id>/", stream_views.stream_run_detail, name="v1_stream_run_detail"),
]

