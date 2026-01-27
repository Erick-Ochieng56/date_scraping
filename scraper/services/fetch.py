from __future__ import annotations

import logging
from typing import Any

import requests


logger = logging.getLogger(__name__)


def fetch_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_html_playwright(
    url: str, *, timeout_ms: int = 30000, wait_until: str = "networkidle"
) -> str:
    """
    Fetch HTML using Playwright for JS-heavy pages.

    Note: Playwright requires browsers installed (e.g., `playwright install`).
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright is not available. Ensure dependency is installed and browsers are installed."
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()

