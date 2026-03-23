from __future__ import annotations

"""
Project-wide constants for the crawler app.
"""

CRAWLER_USER_AGENT = "TranslationLeadCrawlerBot/1.0"

DEFAULT_MAX_PAGES_PER_DOMAIN = 25
DEFAULT_MAX_CRAWL_DEPTH = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS = 1.5

PRIORITY_PATHS: list[str] = [
    "/",
    "/about",
    "/about-us",
    "/who-we-are",
    "/services",
    "/what-we-do",
    "/solutions",
    "/events",
    "/conference",
    "/summit",
    "/forum",
    "/workshop",
    "/news",
    "/blog",
    "/press",
    "/updates",
    "/contact",
    "/contact-us",
    "/reach-us",
    "/programmes",
    "/projects",
    "/initiatives",
]

EMAIL_REGEX = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
