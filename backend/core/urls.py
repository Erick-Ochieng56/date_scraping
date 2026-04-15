from django.conf import settings
from django.urls import path

from core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("ops/trigger-scrape", views.trigger_scrape, name="trigger-scrape"),
    path("ops/trigger-sync", views.trigger_sync, name="trigger-sync"),
    path("ops/auto-create-target", views.auto_create_target, name="auto-create-target"),
]
if not getattr(settings, "SERVE_REACT_APP", False):
    urlpatterns.insert(0, path("", views.home, name="home"))
