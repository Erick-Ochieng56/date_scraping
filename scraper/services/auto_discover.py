from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from scraper.models import ScrapeTargetType

logger = logging.getLogger(__name__)


def detect_platform_type(url: str) -> str | None:
    """
    Detect common platform types from URL.

    Returns platform identifier or None if unknown.
    """
    domain = urlparse(url).netloc.lower().replace("www.", "")

    if "eventbrite.com" in domain or "eventbrite.co.uk" in domain or "eventbrite.ca" in domain:
        return "eventbrite"
    elif "meetup.com" in domain:
        return "meetup"
    elif "facebook.com" in domain or "fb.com" in domain:
        return "facebook"
    elif "eventful.com" in domain:
        return "eventful"
    elif "brownpapertickets.com" in domain:
        return "brownpapertickets"
    elif "ticketmaster.com" in domain:
        return "ticketmaster"

    return None


def get_platform_config(platform: str, base_url: str) -> dict[str, Any] | None:
    """
    Get default config for known platforms.

    Returns config dict with selectors and settings optimised for the platform.
    """
    configs: dict[str, dict[str, Any]] = {
        "eventbrite": {
            "item_selector": (
                ".event-card, .search-event-card-wrapper, "
                "[data-testid='search-result'], .event-tile"
            ),
            "fields": {
                "full_name": (
                    ".event-title, .event-card-title, "
                    "[data-testid='event-title'], h2.event-title"
                ),
                "event_date": (
                    ".event-date, [data-testid='event-date'], .event-card-date, time"
                ),
                "event_name": (
                    ".event-description, .event-card-description, .event-summary"
                ),
                "source_url": (
                    "a.event-card-link@href, "
                    "a[data-testid='event-link']@href, "
                    "a.event-link@href"
                ),
            },
            "next_page_selector": (
                "a.pagination-next, a[aria-label='Next'], "
                "[data-testid='pagination-next']"
            ),
            "max_pages": 5,
            "target_type": ScrapeTargetType.HTML,
            "timeout_seconds": 30,
        },

        # ------------------------------------------------------------------
        # Meetup — React SPA; never reaches networkidle.
        # Strategy:
        #   1. wait_until="domcontentloaded"  (fast, reliable)
        #   2. wait_for_selector on a stable container before grabbing HTML
        #      (handled in fetch.py via the optional wait_for_selector key)
        #   3. Generous timeout so the subprocess has room to breathe.
        #
        # Selectors verified against Meetup's 2025/2026 DOM:
        #   - Event cards live inside <div data-element-name="categoryResults">
        #     or a plain <ul> with li[data-element-name="event-card"]
        # ------------------------------------------------------------------
        "meetup": {
            "item_selector": (
                "[data-element-name='event-card'], "
                "li[data-testid='event-card'], "
                ".event-card"
            ),
            "fields": {
                "full_name": (
                    "[data-element-name='event-title'], "
                    "[data-testid='event-title'], "
                    "h2, h3"
                ),
                "event_date": (
                    "time[datetime], "
                    "[data-element-name='event-date'], "
                    "[data-testid='event-date']"
                ),
                "event_name": (
                    "[data-element-name='event-description'], "
                    "[data-testid='event-description'], "
                    "p"
                ),
                "source_url": "a@href",
            },
            # Wait for at least one event card to appear before capturing HTML.
            # fetch_html_playwright will use this if present.
            "wait_for_selector": "[data-element-name='event-card'], [data-testid='event-card']",
            "next_page_selector": (
                "a[data-testid='pagination-next'], "
                "a[aria-label='Next page']"
            ),
            "max_pages": 3,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            # domcontentloaded fires as soon as the DOM is parsed — SPAs
            # continue loading data via XHR after this point, which is why
            # we also use wait_for_selector above.
            "wait_until": "domcontentloaded",
            "timeout_seconds": 90,  # wall-clock budget; playwright timeout is this * 1000 ms
        },

        "facebook": {
            "item_selector": "[data-testid='event-card'], .event-card, .event-item",
            "fields": {
                "full_name": "[data-testid='event-title'], .event-title, h2, h3",
                "event_date": "[data-testid='event-date'], .event-date, time",
                "event_name": "[data-testid='event-description'], .event-description",
                "source_url": "a[data-testid='event-link']@href, a.event-link@href",
            },
            "next_page_selector": "a[aria-label='Next'], .pagination-next",
            "max_pages": 3,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            "wait_until": "domcontentloaded",
            "timeout_seconds": 60,
        },

        "eventful": {
            "item_selector": ".event-item, .event-card, .event-listing",
            "fields": {
                "full_name": ".event-title, h2, h3",
                "event_date": ".event-date, .date, time",
                "event_name": ".event-description, .description",
                "source_url": "a.event-link@href, a@href",
            },
            "next_page_selector": ".pagination .next, a.next",
            "max_pages": 5,
            "target_type": ScrapeTargetType.HTML,
            "timeout_seconds": 30,
        },

        "brownpapertickets": {
            "item_selector": ".event-item, .event-listing, .event",
            "fields": {
                "full_name": ".event-title, .title, h2",
                "event_date": ".event-date, .date",
                "event_name": ".event-description",
                "source_url": "a.event-link@href",
            },
            "next_page_selector": ".pagination .next",
            "max_pages": 5,
            "target_type": ScrapeTargetType.HTML,
            "timeout_seconds": 30,
        },

        "ticketmaster": {
            "item_selector": ".event-tile, .event-card, [data-testid='event-card']",
            "fields": {
                "full_name": ".event-title, [data-testid='event-title'], h3",
                "event_date": ".event-date, [data-testid='event-date'], time",
                "event_name": ".event-description",
                "source_url": "a.event-link@href, a[data-testid='event-link']@href",
            },
            "next_page_selector": ".pagination-next, a[aria-label='Next']",
            "max_pages": 5,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            "wait_until": "domcontentloaded",
            "timeout_seconds": 60,
        },
    }

    return configs.get(platform)


def auto_create_target(url: str, name: str | None = None) -> dict[str, Any]:
    """
    Auto-generate target config from URL.

    Args:
        url: The URL to scrape
        name: Optional custom name (auto-generated from domain if not provided)

    Returns:
        Dict with target configuration ready for ScrapeTarget creation
    """
    platform = detect_platform_type(url)

    if not name:
        domain = urlparse(url).netloc
        domain_parts = domain.replace("www.", "").split(".")
        platform_name = domain_parts[0].title() if domain_parts else "Auto-Discovered"
        name = f"Auto-{platform_name}"

    config: dict[str, Any] = {
        "name": name,
        "start_url": url,
        "enabled": True,
        "target_type": ScrapeTargetType.HTML,
        "run_every_minutes": 120,
        "config": {
            "item_selector": ".item, .event, .listing, .event-item, .event-card",
            "fields": {
                "full_name": ".title, .name, h2, h3, .event-title",
                "event_date": ".date, .time, [datetime], .event-date",
                "event_name": ".description, .event-description",
                "source_url": "a@href, a.event-link@href",
            },
            "max_pages": 3,
            "timeout_seconds": 30,
        },
    }

    if platform:
        platform_config = get_platform_config(platform, url)
        if platform_config:
            target_type = platform_config.pop("target_type", ScrapeTargetType.HTML)
            config["target_type"] = target_type
            config["config"].update(platform_config)
            logger.info(f"Applied {platform} platform config for {url}")
        else:
            logger.warning(f"Platform '{platform}' detected but no config available")
    else:
        logger.info(f"No known platform detected for {url}, using generic config")

    return config