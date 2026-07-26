from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
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
from crawler.utils import RateLimiter, clean_text, make_soup, normalize_domain_url, normalize_url

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
        # Playwright doesn't expose a Content-Type header here; rely on content sniffing.
        return html, clean_text(html)

    headers = {"User-Agent": CRAWLER_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    html = resp.text
    ct = resp.headers.get("Content-Type", "")
    return html, clean_text(html, content_type=ct)


def extract_internal_links(base_url: str, html: str) -> list[str]:
    """Extract internal links from HTML. Filter to same domain only."""
    base = urlparse(base_url)
    if not base.netloc:
        return []

    soup = make_soup(html)
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


# Sitemap XML namespaces (sites use either none or this)
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAP_NS_DEFAULT = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Max URLs to take from a sitemap as seeds (avoid huge queues)
MAX_SITEMAP_SEEDS = 100


def _fetch_sitemap_urls(base_url: str) -> list[str]:
    """
    Fetch sitemap.xml (or sitemap index) and return same-domain URLs.
    Preserves order; dedupes. Returns [] on any failure.
    """
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return []
    base_netloc = parsed.netloc.lower()
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    headers = {"User-Agent": CRAWLER_USER_AGENT}
    try:
        resp = requests.get(
            sitemap_url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except Exception as e:
        logger.debug("sitemap fetch failed for %s: %s", sitemap_url, e)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.debug("sitemap parse failed for %s: %s", sitemap_url, e)
        return []

    # Handle both <urlset> and <sitemapindex>; support with or without namespace
    def find_all_loc(parent: ET.Element) -> list[str]:
        out: list[str] = []
        for elem in parent.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "loc" and elem.text:
                out.append((elem.text or "").strip())
        return out

    urls: list[str] = []
    root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if root_tag == "sitemapindex":
        # Follow first-level sitemap index (one hop only)
        for loc in find_all_loc(root)[:20]:
            if not loc or not loc.lower().startswith(("http://", "https://")):
                continue
            try:
                r = requests.get(loc, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS)
                r.raise_for_status()
                child = ET.fromstring(r.content)
                for u in find_all_loc(child):
                    if u and urlparse(u).netloc.lower() == base_netloc:
                        nu = normalize_url(u)
                        if nu and nu not in urls:
                            urls.append(nu)
                            if len(urls) >= MAX_SITEMAP_SEEDS:
                                return urls
            except Exception:
                continue
        return urls

    # <urlset>
    for u in find_all_loc(root):
        if u and urlparse(u).netloc.lower() == base_netloc:
            nu = normalize_url(u)
            if nu and nu not in urls:
                urls.append(nu)
                if len(urls) >= MAX_SITEMAP_SEEDS:
                    break
    return urls


def _discover_seed_urls(domain: str) -> list[str]:
    """
    Discover crawl seed URLs from the site instead of guessing paths.
    Uses sitemap.xml when present; always includes the homepage.
    This avoids 404s on sites that use PascalCase or nested paths (e.g. /ISA/About-ISA).
    """
    base = domain.rstrip("/")
    homepage = base + "/" if not base.endswith("/") else base
    homepage = normalize_url(homepage)
    if not homepage:
        return []

    sitemap_urls = _fetch_sitemap_urls(base)
    seen: set[str] = set()
    out: list[str] = []

    # Prefer homepage first so we always crawl it and discover links
    if homepage not in seen:
        out.append(homepage)
        seen.add(homepage)
    for u in sitemap_urls:
        if u and u not in seen:
            out.append(u)
            seen.add(u)
    # If no sitemap, we still have the homepage; BFS will discover links from there
    return out


def _path_is_priority(url: str) -> bool:
    """True when url's path matches one of PRIORITY_PATHS (about/services/events/etc.) —
    used to explore these before other discovered links within the max_pages budget."""
    path = urlparse(url).path.rstrip("/").lower() or "/"
    return any(path == p or path.endswith(p) for p in PRIORITY_PATHS)


def _looks_js_heavy(text: str, html: str) -> bool:
    # If we get almost no text but lots of scripts, assume JS rendering.
    if len((text or "").strip()) >= 250:
        return False
    script_count = html.lower().count("<script")
    return script_count >= 10


def crawl_domain(
    domain_obj: DiscoveredDomain,
    *,
    rate_limit_seconds: float | None = None,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """
    Main crawl function for a single domain.

    rate_limit_seconds/max_pages/max_depth override the module defaults when
    given — previously CRAWLER_RATE_LIMIT_SECONDS was computed and snapshotted
    onto CrawlRun.config but this function always used the hardcoded
    DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS regardless, so operators setting that
    env var to slow down or speed up crawling saw no effect. Callers without a
    run context (tests, ad hoc use) can omit these and get the same defaults
    as before.

    Returns dict:
      {
        'pages': [{'url': str, 'text': str, 'html': str}],
        'emails': list[str],
        'phones': list[str],
        'pages_crawled': int,
        'error': str | None
      }
    """
    base = (domain_obj.domain or "").strip()
    if "://" not in base:
        base = normalize_domain_url(base)
    if not base:
        return {
            "pages": [],
            "emails": [],
            "phones": [],
            "pages_crawled": 0,
            "error": "Invalid domain",
        }
    limiter = RateLimiter(
        seconds=rate_limit_seconds if rate_limit_seconds is not None else DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS
    )

    max_pages = max_pages if max_pages is not None else DEFAULT_MAX_PAGES_PER_DOMAIN
    max_depth = max_depth if max_depth is not None else DEFAULT_MAX_CRAWL_DEPTH

    visited: set[str] = set()
    seeds = _discover_seed_urls(base)
    landing = (getattr(domain_obj, "source_url", None) or "").strip()
    if landing:
        landing = normalize_url(landing)
        bp = urlparse(base)
        lp = urlparse(landing)
        if (
            landing
            and lp.scheme in {"http", "https"}
            and lp.netloc.lower().removeprefix("www.")
            == bp.netloc.lower().removeprefix("www.")
        ):
            seeds = [landing] + [s for s in seeds if s != landing]

    queue: deque[tuple[str, int]] = deque((u, 0) for u in seeds)

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

        # Explore newly discovered links, but jump PRIORITY_PATHS (about/services/events/
        # contact/programmes) to the front of the queue so they're reached within the
        # max_pages budget even on a large site, instead of being crowded out by whatever
        # order links happen to appear on the page.
        try:
            new_links = [
                link for link in extract_internal_links(base_url=url, html=html) if link not in visited
            ]
            priority_links = [link for link in new_links if _path_is_priority(link)]
            normal_links = [link for link in new_links if not _path_is_priority(link)]
            for link in reversed(priority_links):
                queue.appendleft((link, depth + 1))
            for link in normal_links:
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

