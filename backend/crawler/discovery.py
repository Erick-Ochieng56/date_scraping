from __future__ import annotations

"""
Discovery returns ``DiscoveryHit`` rows: ``domain`` is the normalized site base
(``https://host``) and ``source_url`` is the SERP result URL (path preserved).

For NGO / event pages, discovery queries often work better with operators such as
``inurl:events``, ``inurl:calendar``, or ``site:.org`` combined with buyer keywords.
"""

import logging
import os
from typing import Any, Iterable, TypedDict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from crawler.models import CrawlSource, DiscoveredDomain
from crawler.utils import normalize_domain_url, normalize_url

logger = logging.getLogger(__name__)

SERPER_BASE_URL = "https://google.serper.dev/search"


class DiscoveryHit(TypedDict):
    """Normalized base domain URL plus the SERP landing page that produced it."""

    domain: str
    source_url: str


def _get_serper_api_key() -> str | None:
    """Return Serper API key if set, else None."""
    key = (os.getenv("SERPER_API_KEY") or "").strip()
    return key if key else None


def _same_registrable_host(a: str, b: str) -> bool:
    la = urlparse(a).netloc.lower().removeprefix("www.")
    lb = urlparse(b).netloc.lower().removeprefix("www.")
    return bool(la and la == lb)


def _landing_path_rank(url: str) -> int:
    """Prefer deeper paths and URLs with query (e.g. tender detail pages)."""
    p = urlparse((url or "").strip())
    path = (p.path or "").strip("/")
    segs = len(path.split("/")) if path else 0
    q = 1 if (p.query or "").strip() else 0
    return segs * 10 + q


def should_replace_source_url(existing: str, new: str, *, domain_base: str) -> bool:
    """Whether ``new`` is a strictly better landing URL than ``existing``."""
    new = (new or "").strip()
    if not new or not _same_registrable_host(new, domain_base):
        return False
    old = (existing or "").strip()
    if not old:
        return True
    return _landing_path_rank(new) > _landing_path_rank(old)


def coerce_discovery_hit(item: Any) -> DiscoveryHit | None:
    """Normalize a hit dict or legacy URL string into a ``DiscoveryHit``."""
    if isinstance(item, str):
        u = item.strip()
        if not u:
            return None
        if "://" not in u:
            u = "https://" + u.lstrip("/")
        base = normalize_domain_url(u)
        if not base:
            return None
        landing = normalize_url(u) or base
        if not _same_registrable_host(landing, base):
            landing = base
        return {"domain": base, "source_url": landing}
    if not isinstance(item, dict):
        return None
    dom = (item.get("domain") or "").strip()
    src = (item.get("source_url") or item.get("landing_url") or "").strip()
    if dom and "://" not in dom:
        dom = "https://" + dom.lstrip("/")
    if src and "://" not in src:
        src = "https://" + src.lstrip("/")
    base = normalize_domain_url(dom or src)
    if not base:
        return None
    landing = normalize_url(src) if src else base
    if not landing or not _same_registrable_host(landing, base):
        landing = base
    # URLField is NOT NULL at DB level in some deployments; never return an empty source_url.
    if not (landing or "").strip():
        landing = base
    return {"domain": base, "source_url": landing}


def discovery_hits_from_user_payload(urls: list[Any]) -> list[DiscoveryHit]:
    """Build hits from manual queue API payloads (strings or {domain, source_url})."""
    out: list[DiscoveryHit] = []
    for raw in urls:
        hit = coerce_discovery_hit(raw)
        if hit:
            out.append(hit)
    return out


def discover_websites_serper(query: str, max_results: int = 20) -> list[DiscoveryHit]:
    """
    Discover URLs using Serper.dev. Preserves each organic ``link`` as ``source_url``
    while ``domain`` stays the normalized site base (https://host) for crawling.
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

    by_domain: dict[str, DiscoveryHit] = {}
    order: list[str] = []

    def consider_link(link: str) -> None:
        link = (link or "").strip()
        if not link or not (
            link.lower().startswith("http://") or link.lower().startswith("https://")
        ):
            return
        base = normalize_domain_url(link)
        if not base:
            return
        landing = normalize_url(link) or base
        if not _same_registrable_host(landing, base):
            landing = base
        if base not in by_domain:
            if len(order) >= max_results:
                return
            by_domain[base] = {"domain": base, "source_url": landing}
            order.append(base)
        else:
            prev = by_domain[base]["source_url"]
            if should_replace_source_url(prev, landing, domain_base=base):
                by_domain[base]["source_url"] = landing

    organic = data.get("organic") or []
    for item in organic:
        consider_link(item.get("link") or "")
        if len(order) >= max_results:
            break

    if len(order) < max_results:
        for item in organic:
            for sitelink in item.get("sitelinks") or []:
                consider_link(sitelink.get("link") or "")
                if len(order) >= max_results:
                    break
            if len(order) >= max_results:
                break

    hits = [by_domain[k] for k in order]
    if not hits:
        logger.info("Serper discovery returned no domains for query=%r", q)
    else:
        logger.info("Serper discovery found %d domain(s) for query=%r", len(hits), q)
    return hits[:max_results]


def discover_websites_bing(query: str, max_results: int = 20) -> list[DiscoveryHit]:
    """Bing HTML scrape; preserves each result href as ``source_url``."""
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

    by_domain: dict[str, DiscoveryHit] = {}
    order: list[str] = []

    def consider_href(href: str) -> None:
        href = (href or "").strip()
        href_lower = href.lower()
        if not (href_lower.startswith("http://") or href_lower.startswith("https://")):
            return
        if "bing.com" in href_lower:
            return
        base = normalize_domain_url(href)
        if not base:
            return
        landing = normalize_url(href) or base
        if not _same_registrable_host(landing, base):
            landing = base
        if base not in by_domain:
            if len(order) >= max_results:
                return
            by_domain[base] = {"domain": base, "source_url": landing}
            order.append(base)
        else:
            prev = by_domain[base]["source_url"]
            if should_replace_source_url(prev, landing, domain_base=base):
                by_domain[base]["source_url"] = landing

    for a in soup.select("li.b_algo h2 a[href]"):
        consider_href(a.get("href") or "")
        if len(order) >= max_results:
            break

    if not order:
        main = soup.select_one("#b_results") or soup
        for a in main.select("a[href]"):
            consider_href(a.get("href") or "")
            if len(order) >= max_results:
                break

    hits = [by_domain[k] for k in order]
    if not hits:
        logger.info("Bing discovery returned no domains for query=%r", q)
    return hits[:max_results]


def discover_websites(query: str, max_results: int = 20) -> list[DiscoveryHit]:
    """
    Discover sites for a query.

    Uses Serper when ``SERPER_API_KEY`` is set; otherwise Bing scraping.
    Returns ``DiscoveryHit`` rows: ``domain`` is ``https://host`` (no path),
    ``source_url`` is the SERP landing URL (may include path/query).
    """
    q = (query or "").strip()
    if not q:
        return []

    if _get_serper_api_key():
        hits = discover_websites_serper(q, max_results=max_results)
        if hits:
            return hits
        logger.info("Serper returned no results; falling back to Bing for query=%r", q)

    return discover_websites_bing(q, max_results=max_results)


def normalize_domain(url: str) -> str:
    """Extract clean domain base from any URL (https://host, no path)."""
    return normalize_domain_url(url)


def save_discovered_domains(
    hits: Iterable[DiscoveryHit | str | dict[str, Any]],
    source: CrawlSource | None,
    owner_id: int | None = None,
) -> int:
    """
    Upsert ``DiscoveredDomain`` rows. Merges a better ``source_url`` when re-discovered.

    Returns count of newly created rows.
    """
    created = 0
    own = owner_id or (getattr(source, "owner_id", None) if source else None)
    for raw in hits:
        hit = coerce_discovery_hit(raw)
        if not hit:
            continue
        dom = hit["domain"]
        src = (hit.get("source_url") or dom or "").strip() or dom
        defaults = {
            "source": source,
            "owner_id": own,
            "priority": source.priority if source else 5,
            "crawl_status": "pending",
            "source_url": src,
        }
        obj, was_created = DiscoveredDomain.objects.get_or_create(
            domain=dom,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            update_fields: list[str] = []
            if source and obj.source_id is None:
                obj.source = source
                update_fields.append("source")
            if should_replace_source_url(obj.source_url, src, domain_base=dom):
                obj.source_url = src
                update_fields.append("source_url")
            if source and obj.priority > source.priority:
                obj.priority = source.priority
                update_fields.append("priority")
            if update_fields:
                obj.save(update_fields=update_fields)
    return created
