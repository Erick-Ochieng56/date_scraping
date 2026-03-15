from __future__ import annotations

import logging
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from crawler.models import CrawlSource, DiscoveredDomain
from crawler.utils import normalize_domain_url

logger = logging.getLogger(__name__)


def discover_websites(query: str, max_results: int = 20) -> list[str]:
    """
    Discover website URLs for a given query by scraping Bing search results.

    Google tends to block automated scraping; Bing is typically more tolerant.
    Returns a list of normalized domain URLs (e.g., https://example.com).
    """
    q = (query or "").strip()
    if not q:
        return []

    url = "https://www.bing.com/search"
    params = {"q": q, "count": str(max_results)}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Bing discovery failed for query=%r: %s", q, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    out: list[str] = []

    # Primary: classic Bing SERP layout
    for a in soup.select("li.b_algo h2 a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        # Ignore non-web links
        href_lower = href.lower()
        if not (href_lower.startswith("http://") or href_lower.startswith("https://")):
            continue
        norm = normalize_domain(href)
        if norm and norm not in out:
            out.append(norm)
        if len(out) >= max_results:
            break

    # Fallback: more generic selection inside main results container
    if not out:
        main = soup.select_one("#b_results") or soup
        for a in main.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            href_lower = href.lower()
            # Skip non-http(s) and internal/navigation links (javascript:, #, mailto:, bing UI, etc.)
            if not (href_lower.startswith("http://") or href_lower.startswith("https://")):
                continue
            if "bing.com" in href_lower:
                continue
            norm = normalize_domain(href)
            if norm and norm not in out:
                out.append(norm)
            if len(out) >= max_results:
                break

    if not out:
        logger.info("Bing discovery returned no domains for query=%r", q)
    return out


def normalize_domain(url: str) -> str:
    """Extract clean domain from any URL. Returns https://domain.com."""
    return normalize_domain_url(url)


def save_discovered_domains(urls: Iterable[str], source: CrawlSource) -> int:
    """
    Save domains to DiscoveredDomain.
    Skip duplicates (get_or_create on domain field).
    Returns count of NEW domains saved.
    """
    created = 0
    for u in urls:
        dom = normalize_domain(u)
        if not dom:
            continue
        obj, was_created = DiscoveredDomain.objects.get_or_create(
            domain=dom,
            defaults={"source": source, "priority": source.priority, "crawl_status": "pending"},
        )
        if was_created:
            created += 1
        else:
            # If existing record is disabled/failed, we can still raise priority.
            if obj.priority > source.priority:
                obj.priority = source.priority
                obj.save(update_fields=["priority"])
    return created
