from __future__ import annotations

import json
import time

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, StreamingHttpResponse
from django.views.decorators.http import require_GET

from crawler.models import CrawlRun
from dashboard.permissions import dashboard_api_user
from scraper.models import ScrapeRun


def _sse_event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, cls=DjangoJSONEncoder)}\n\n"


def _run_snapshot(run_id: int | None = None) -> dict:
    scrape_qs = ScrapeRun.objects.all()
    crawl_qs = CrawlRun.objects.all()
    if run_id is not None:
        scrape_qs = scrape_qs.filter(id=run_id)
        crawl_qs = crawl_qs.filter(id=run_id)

    scrape = list(
        scrape_qs.order_by("-started_at")
        .values("id", "status", "started_at", "finished_at", "item_count", "created_leads", "updated_leads")[:20]
    )
    crawl = list(
        crawl_qs.order_by("-started_at")
        .values("id", "status", "started_at", "finished_at", "domains_queued", "prospects_created", "prospects_updated")[:20]
    )
    return {"scrape_runs": scrape, "crawl_runs": crawl}


@require_GET
@dashboard_api_user
def stream_runs(request: HttpRequest) -> StreamingHttpResponse:
    def event_stream():
        try:
            while True:
                payload = _run_snapshot()
                yield _sse_event("runs", payload)
                # Keep interval short for near-live non-technical UX.
                time.sleep(3)
        except GeneratorExit:
            return

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_GET
@dashboard_api_user
def stream_run_detail(request: HttpRequest, run_id: int) -> StreamingHttpResponse:
    def event_stream():
        try:
            while True:
                payload = _run_snapshot(run_id=run_id)
                yield _sse_event("run_detail", payload)
                time.sleep(3)
        except GeneratorExit:
            return

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response

