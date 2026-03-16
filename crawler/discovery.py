from __future__ import annotations

import logging
import os
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from crawler.models import CrawlSource, DiscoveredDomain
from crawler.utils import normalize_domain_url

logger = logging.getLogger(__name__)

SERPER_BASE_URL = "https://google.serper.dev/search"


def _get_serper_api_key() -> str | None:
    """Return Serper API key if set, else None."""
    key = (os.getenv("SERPER_API_KEY") or "").strip()
    return key if key else None


def discover_websites_serper(query: str, max_results: int = 20) -> list[str]:
    """
    Discover website URLs using Serper.dev Google Search API.

    Requires SERPER_API_KEY to be set. Returns a list of normalized domain URLs.
    """
    q = (query or "").strip()
    if not q:
        return []

    api_key = _get_serper_api_key()
    if not api_key:
        logger.debug("SERPER_API_KEY not set; skipping Serper discovery")
        return []

    payload = {"q": q, "num": min(max_results, 100)}
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            SERPER_BASE_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Serper API request failed for query=%r: %s", q, exc)
        return []
    except ValueError as exc:
        logger.warning("Serper API invalid JSON for query=%r: %s", q, exc)
        return []

    out: list[str] = []
    organic = data.get("organic") or []
    for item in organic:
        link = (item.get("link") or "").strip()
        if not link or not (
            link.lower().startswith("http://") or link.lower().startswith("https://")
        ):
            continue
        norm = normalize_domain(link)
        if norm and norm not in out:
            out.append(norm)
        if len(out) >= max_results:
            break

    # Include sitelinks from organic results for more coverage
    if len(out) < max_results:
        for item in organic:
            for sitelink in item.get("sitelinks") or []:
                link = (sitelink.get("link") or "").strip()
                if not link or not (
                    link.lower().startswith("http://")
                    or link.lower().startswith("https://")
                ):
                    continue
                norm = normalize_domain(link)
                if norm and norm not in out:
                    out.append(norm)
                if len(out) >= max_results:
                    break
            if len(out) >= max_results:
                break

    if not out:
        logger.info("Serper discovery returned no domains for query=%r", q)
    else:
        logger.info("Serper discovery found %d domain(s) for query=%r", len(out), q)
    return out[:max_results]


def discover_websites_bing(query: str, max_results: int = 20) -> list[str]:
    """
    Discover website URLs by scraping Bing search results.

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


def discover_websites(query: str, max_results: int = 20) -> list[str]:
    """
    Discover website URLs for a given query.

    Uses Serper.dev (Google Search API) when SERPER_API_KEY is set;
    otherwise falls back to Bing scraping. Returns a list of normalized
    domain URLs (e.g., https://example.com).
    """
    q = (query or "").strip()
    if not q:
        return []

    if _get_serper_api_key():
        urls = discover_websites_serper(q, max_results=max_results)
        if urls:
            return urls
        logger.info("Serper returned no results; falling back to Bing for query=%r", q)

    return discover_websites_bing(q, max_results=max_results)


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
