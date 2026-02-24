from django.urls import path
from . import api_views, export_views, views, wizard_views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardHomeView.as_view(), name='index'),
    path('activity/', views.ActivityLogListView.as_view(), name='activity_log'),
    path('errors/', views.ErrorMonitoringView.as_view(), name='error_monitoring'),
    path('targets/', views.TargetListView.as_view(), name='targets'),
    path('targets/<int:pk>/', views.TargetDetailView.as_view(), name='target_detail'),
    path('targets/<int:pk>/edit/', views.TargetEditView.as_view(), name='target_edit'),
    path('targets/wizard/', views.TargetWizardView.as_view(), name='target_wizard'),
    path('runs/', views.RunListView.as_view(), name='runs'),
    path('runs/<int:pk>/', views.RunDetailView.as_view(), name='run_detail'),
    path('prospects/', views.ProspectListView.as_view(), name='prospects'),
    path('prospects/add/', views.ProspectCreateView.as_view(), name='prospect_add'),
    path('prospects/<int:pk>/', views.ProspectDetailView.as_view(), name='prospect_detail'),
    path('leads/', views.LeadListView.as_view(), name='leads'),
    path('leads/add/', views.LeadCreateView.as_view(), name='lead_add'),
    path('leads/<int:pk>/', views.LeadDetailView.as_view(), name='lead_detail'),
    
    # API endpoints - Scraping
    path('api/trigger-scrape/', api_views.api_trigger_scrape, name='api_trigger_scrape'),
    path('api/runs/<int:run_id>/retry/', api_views.api_retry_run, name='api_retry_run'),
    path('api/runs/<int:run_id>/status/', api_views.api_get_run_status, name='api_get_run_status'),
    
    # API endpoints - Prospects (bulk)
    path('api/prospects/bulk/mark-contacted/', api_views.api_prospect_bulk_mark_contacted, name='api_prospect_bulk_mark_contacted'),
    path('api/prospects/bulk/convert/', api_views.api_prospect_bulk_convert, name='api_prospect_bulk_convert'),
    path('api/prospects/bulk/reject/', api_views.api_prospect_bulk_reject, name='api_prospect_bulk_reject'),
    
    # API endpoints - Prospects (single)
    path('api/prospects/<int:prospect_id>/mark-contacted/', api_views.api_prospect_mark_contacted, name='api_prospect_mark_contacted'),
    path('api/prospects/<int:prospect_id>/convert/', api_views.api_prospect_convert, name='api_prospect_convert'),
    path('api/prospects/<int:prospect_id>/reject/', api_views.api_prospect_reject, name='api_prospect_reject'),
    
    # API endpoints - Leads (bulk)
    path('api/leads/bulk/mark-interested/', api_views.api_lead_bulk_mark_interested, name='api_lead_bulk_mark_interested'),
    path('api/leads/bulk/sync-crm/', api_views.api_lead_bulk_sync_crm, name='api_lead_bulk_sync_crm'),
    path('api/leads/bulk/reject/', api_views.api_lead_bulk_reject, name='api_lead_bulk_reject'),
    
    # API endpoints - Leads (single)
    path('api/leads/<int:lead_id>/mark-interested/', api_views.api_lead_mark_interested, name='api_lead_mark_interested'),
    path('api/leads/<int:lead_id>/sync-crm/', api_views.api_lead_sync_crm, name='api_lead_sync_crm'),
    path('api/leads/<int:lead_id>/reject/', api_views.api_lead_reject, name='api_lead_reject'),
    
    # Export endpoints
    path('export/prospects/csv/', export_views.export_prospects_csv, name='export_prospects_csv'),
    path('export/leads/csv/', export_views.export_leads_csv, name='export_leads_csv'),
    
    # Wizard endpoints
    path('wizard/detect-platform/', wizard_views.wizard_detect_platform, name='wizard_detect_platform'),
    path('wizard/create-target/', wizard_views.wizard_create_target, name='wizard_create_target'),
    
    # Notifications endpoints
    path('api/notifications/', api_views.api_notifications, name='api_notifications'),
    path('api/notifications/<int:notif_id>/read/', api_views.api_notification_read, name='api_notification_read'),
]

