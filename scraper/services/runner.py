from __future__ import annotations

import logging
from urllib.parse import urljoin

from scraper.models import ScrapeTarget, ScrapeTargetType
from scraper.services.extract import extract_items, extract_next_page_url
from scraper.services.fetch import fetch_html, fetch_html_playwright


logger = logging.getLogger(__name__)


def run_target(target: ScrapeTarget) -> list[dict]:
    """
    Execute a target scrape based on `ScrapeTarget.config`.

    Expected config keys (minimal):
      - item_selector: CSS selector for each item row (required)
      - fields: dict mapping field -> selector/spec (required)
      - next_page_selector: CSS selector for next page link (optional)
      - max_pages: int (optional; default 1)
      - headers: dict (optional)
      - timeout_seconds: int (optional)
      - wait_until: playwright wait_until (optional)
    """
    cfg = target.config or {}
    item_selector = cfg.get("item_selector") or cfg.get("items_selector")
    fields = cfg.get("fields") or {}
    if not item_selector:
        raise ValueError(f"ScrapeTarget {target.id} missing config.item_selector")

    max_pages = int(cfg.get("max_pages") or 1)
    headers = cfg.get("headers") or None
    timeout_seconds = int(cfg.get("timeout_seconds") or 30)
    wait_until = str(cfg.get("wait_until") or "networkidle")

    url = target.start_url
    all_items: list[dict] = []

    for page_num in range(1, max_pages + 1):
        if target.target_type == ScrapeTargetType.PLAYWRIGHT:
            html = fetch_html_playwright(
                url, timeout_ms=timeout_seconds * 1000, wait_until=wait_until
            )
        else:
            html = fetch_html(url, headers=headers, timeout=timeout_seconds)

        items = extract_items(html, item_selector=item_selector, fields=fields)
        for it in items:
            it.setdefault("_page_url", url)
            it.setdefault("_target_id", target.id)
            it.setdefault("_target_name", target.name)
        all_items.extend(items)

        next_sel = cfg.get("next_page_selector") or ""
        if not next_sel:
            break
        next_href = extract_next_page_url(html, next_page_selector=next_sel)
        if not next_href:
            break

        url = urljoin(url, next_href)
        logger.info("ScrapeTarget %s page %s -> %s", target.id, page_num, url)

    return all_items

