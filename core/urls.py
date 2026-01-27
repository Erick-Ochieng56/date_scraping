from django.urls import path

from core import views


urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("ops/trigger-scrape", views.trigger_scrape, name="trigger-scrape"),
    path("ops/trigger-sync", views.trigger_sync, name="trigger-sync"),
]

