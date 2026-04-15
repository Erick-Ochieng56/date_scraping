"""
URL configuration for leads_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()

if getattr(settings, "SERVE_REACT_APP", False):
    from core import views as core_views

    urlpatterns.append(re_path(r"^(?P<spa_path>.*)$", core_views.react_spa_catch_all))
