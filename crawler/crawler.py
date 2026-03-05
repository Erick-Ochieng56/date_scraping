from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from crawler.constants import (
    CRAWLER_USER_AGENT,
    DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS,
    DEFAULT_MAX_CRAWL_DEPTH,
    DEFAULT_MAX_PAGES_PER_DOMAIN,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PRIORITY_PATHS,
)
from crawler.models import DiscoveredDomain
from crawler.utils import RateLimiter, clean_text, normalize_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawledPage:
    url: str
    html: str
    text: str


def fetch_page(url: str, use_playwright: bool = False) -> tuple[str, str]:
    """
    Fetch page HTML and extracted text. Returns (html, text).

    Playwright is a fallback only; use it when JS-heavy sites render empty HTML.
    """
    if use_playwright:
        # Reuse existing Playwright fetcher to avoid duplicating subprocess logic.
        from scraper.services.fetch import fetch_html_playwright

        html = fetch_html_playwright(
            url,
            timeout_ms=int(DEFAULT_REQUEST_TIMEOUT_SECONDS * 1000),
            wait_until="domcontentloaded",
            wait_for_selector=None,
        )
        return html, clean_text(html)

    headers = {"User-Agent": CRAWLER_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    html = resp.text
    return html, clean_text(html)


def extract_internal_links(base_url: str, html: str) -> list[str]:
    """Extract internal links from HTML. Filter to same domain only."""
    base = urlparse(base_url)
    if not base.netloc:
        return []

    soup = BeautifulSoup(html or "", "lxml")
    out: list[str] = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("mailto:"):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if not absolute:
            continue
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() != base.netloc.lower():
            continue
        if absolute not in out:
            out.append(absolute)
    return out


_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def is_allowed_by_robots(url: str) -> bool:
    """Check robots.txt before crawling every domain."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False

    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _ROBOTS_CACHE.get(base)
    if rp is None:
        rp = RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            # If robots can't be fetched, default to allowed.
            logger.debug("robots.txt fetch failed for %s; default allow", base)
        _ROBOTS_CACHE[base] = rp
    try:
        return rp.can_fetch(CRAWLER_USER_AGENT, url)
    except Exception:
        return True


def _prioritized_seed_urls(domain: str) -> list[str]:
    base = domain.rstrip("/")
    urls: list[str] = []
    for path in PRIORITY_PATHS:
        if path == "/":
            u = base + "/"
        else:
            u = base + path
        urls.append(u)
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        nu = normalize_url(u)
        if nu and nu not in seen:
            out.append(nu)
            seen.add(nu)
    return out


def _looks_js_heavy(text: str, html: str) -> bool:
    # If we get almost no text but lots of scripts, assume JS rendering.
    if len((text or "").strip()) >= 250:
        return False
    script_count = html.lower().count("<script")
    return script_count >= 10


def crawl_domain(domain_obj: DiscoveredDomain) -> dict[str, Any]:
    """
    Main crawl function for a single domain.

    Returns dict:
      {
        'pages': [{'url': str, 'text': str, 'html': str}],
        'emails': list[str],
        'phones': list[str],
        'pages_crawled': int,
        'error': str | None
      }
    """
    base = domain_obj.domain
    limiter = RateLimiter(seconds=DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS)

    max_pages = DEFAULT_MAX_PAGES_PER_DOMAIN
    max_depth = DEFAULT_MAX_CRAWL_DEPTH

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque((u, 0) for u in _prioritized_seed_urls(base))

    pages: list[CrawledPage] = []
    error: str | None = None

    while queue and len(pages) < max_pages:
        url, depth = queue.popleft()
        url = normalize_url(url)
        if not url or url in visited:
            continue
        visited.add(url)

        if not is_allowed_by_robots(url):
            logger.info("robots disallow: %s", url)
            continue

        try:
            limiter.wait(domain=urlparse(url).netloc.lower())
            html, text = fetch_page(url, use_playwright=False)
            if _looks_js_heavy(text, html):
                try:
                    html, text = fetch_page(url, use_playwright=True)
                except Exception as exc:
                    logger.debug("Playwright fallback failed for %s: %s", url, exc)
        except Exception as exc:
            logger.info("Fetch failed for %s: %s", url, exc)
            error = str(exc)
            continue

        pages.append(CrawledPage(url=url, html=html, text=text))

        if depth >= max_depth:
            continue

        # Extract more internal links; we will prioritize "priority paths" via seed URLs,
        # but still explore additional discovered links.
        try:
            for link in extract_internal_links(base_url=url, html=html):
                if link not in visited:
                    queue.append((link, depth + 1))
        except Exception:
            continue

    from crawler.extractor import extract_emails, extract_phones

    combined_text = "\n".join(p.text for p in pages)
    emails = extract_emails(combined_text)
    phones = extract_phones(combined_text)

    return {
        "pages": [{"url": p.url, "text": p.text, "html": p.html} for p in pages],
        "emails": emails,
        "phones": phones,
        "pages_crawled": len(pages),
        "error": error,
    }

