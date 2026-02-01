from __future__ import annotations

import logging
from typing import Any

import requests


logger = logging.getLogger(__name__)


def fetch_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error fetching {url}: {e}")
        raise ConnectionError(
            f"Failed to connect to {url}. Check your internet connection and DNS settings."
        ) from e
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout fetching {url} after {timeout}s")
        raise TimeoutError(f"Request to {url} timed out after {timeout} seconds") from e
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching {url}: {e}")
        raise


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
            try:
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                return page.content()
            except Exception as e:
                error_msg = str(e)
                if "ERR_NAME_NOT_RESOLVED" in error_msg or "getaddrinfo failed" in error_msg:
                    raise ConnectionError(
                        f"DNS resolution failed for {url}. Check your internet connection and DNS settings."
                    ) from e
                elif "Timeout" in error_msg or "timeout" in error_msg.lower():
                    raise TimeoutError(
                        f"Page load timeout for {url} after {timeout_ms}ms. The page may be too slow or unresponsive."
                    ) from e
                raise
        finally:
            browser.close()

