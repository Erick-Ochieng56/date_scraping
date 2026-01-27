from __future__ import annotations

import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leads_app.settings")

app = Celery("leads_app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

