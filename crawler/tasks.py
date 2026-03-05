from __future__ import annotations

"""
Celery autodiscovery shim for the crawler pipeline.

Celery's Django autodiscover searches installed apps for a `tasks` module.
The project requirements also include `tasks/crawler_tasks.py` at repo root.
We import those task definitions here so Celery can discover them.
"""

from tasks.crawler_tasks import (  # noqa: F401
    analyze_domain_task,
    crawl_domain_task,
    discover_websites_task,
    score_and_create_prospect_task,
)

