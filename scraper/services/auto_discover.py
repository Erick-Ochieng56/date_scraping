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
    domain = urlparse(url).netloc.lower()
    
    # Remove www. prefix for matching
    domain = domain.replace("www.", "")
    
    if "eventbrite.com" in domain:
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
    elif "eventbrite.co.uk" in domain or "eventbrite.ca" in domain:
        return "eventbrite"  # Eventbrite international domains
    
    return None


def get_platform_config(platform: str, base_url: str) -> dict[str, Any] | None:
    """
    Get default config for known platforms.
    
    Returns config dict with selectors and settings optimized for the platform.
    """
    configs: dict[str, dict[str, Any]] = {
        "eventbrite": {
            "item_selector": ".event-card, .search-event-card-wrapper, [data-testid='search-result'], .event-tile",
            "fields": {
                "full_name": ".event-title, .event-card-title, [data-testid='event-title'], h2.event-title",
                "event_date": ".event-date, [data-testid='event-date'], .event-card-date, time",
                "event_name": ".event-description, .event-card-description, .event-summary",
                "source_url": "a.event-card-link@href, a[data-testid='event-link']@href, a.event-link@href"
            },
            "next_page_selector": "a.pagination-next, a[aria-label='Next'], [data-testid='pagination-next'], .pagination a:contains('Next')",
            "max_pages": 5,
            "target_type": ScrapeTargetType.HTML,
            "timeout_seconds": 30,
        },
        "meetup": {
            "item_selector": ".eventCard, [data-testid='event-card'], .event-listing, .event-card",
            "fields": {
                "full_name": ".eventCard-title, [data-testid='event-title'], .event-title, h3.eventCard-title",
                "event_date": ".eventCard-date, [data-testid='event-date'], .event-date, time",
                "event_name": ".eventCard-description, .event-description, .event-summary",
                "source_url": "a.eventCard-link@href, a[data-testid='event-link']@href, a.event-link@href"
            },
            "next_page_selector": "a[data-testid='pagination-next'], .pagination-next, a.pagination-link:contains('Next')",
            "max_pages": 3,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            "timeout_seconds": 45,
            "wait_until": "networkidle",
        },
        "facebook": {
            "item_selector": "[data-testid='event-card'], .event-card, .event-item",
            "fields": {
                "full_name": "[data-testid='event-title'], .event-title, h2, h3",
                "event_date": "[data-testid='event-date'], .event-date, time",
                "event_name": "[data-testid='event-description'], .event-description",
                "source_url": "a[data-testid='event-link']@href, a.event-link@href"
            },
            "next_page_selector": "a[aria-label='Next'], .pagination-next",
            "max_pages": 3,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            "timeout_seconds": 60,
            "wait_until": "networkidle",
        },
        "eventful": {
            "item_selector": ".event-item, .event-card, .event-listing",
            "fields": {
                "full_name": ".event-title, h2, h3",
                "event_date": ".event-date, .date, time",
                "event_name": ".event-description, .description",
                "source_url": "a.event-link@href, a@href"
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
                "source_url": "a.event-link@href"
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
                "source_url": "a.event-link@href, a[data-testid='event-link']@href"
            },
            "next_page_selector": ".pagination-next, a[aria-label='Next']",
            "max_pages": 5,
            "target_type": ScrapeTargetType.PLAYWRIGHT,
            "timeout_seconds": 45,
            "wait_until": "networkidle",
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
    
    # Generate name if not provided
    if not name:
        domain = urlparse(url).netloc
        domain_parts = domain.replace("www.", "").split(".")
        if domain_parts:
            platform_name = domain_parts[0].title()
        else:
            platform_name = "Auto-Discovered"
        name = f"Auto-{platform_name}"
    
    # Start with generic fallback config
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
                "source_url": "a@href, a.event-link@href"
            },
            "max_pages": 3,
            "timeout_seconds": 30,
        }
    }
    
    # Override with platform-specific config if available
    if platform:
        platform_config = get_platform_config(platform, url)
        if platform_config:
            # Extract target_type separately (it's not part of config dict)
            target_type = platform_config.pop("target_type", ScrapeTargetType.HTML)
            config["target_type"] = target_type
            
            # Merge platform config into the config dict
            config["config"].update(platform_config)
            logger.info(f"Applied {platform} platform config for {url}")
        else:
            logger.warning(f"Platform '{platform}' detected but no config available")
    else:
        logger.info(f"No known platform detected for {url}, using generic config")
    
    return config

