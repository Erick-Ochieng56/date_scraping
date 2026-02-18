"""
Two-Stage Scraping - Enrichment Service

Stage 1: Listing pages (fast) → Basic info + URLs
Stage 2: Detail pages (slow) → Complete data including contact info

This service visits individual event/profile pages to extract additional
information like organizer contact details, full descriptions, etc.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from bs4 import BeautifulSoup

from scraper.services.extract import extract_items
from scraper.services.fetch import fetch_html, fetch_html_playwright

logger = logging.getLogger(__name__)


class DetailPageEnricher:
    """Extract additional fields from detail pages."""

    def __init__(
        self, url: str, platform: str = "generic", use_playwright: bool = False
    ):
        """
        Initialize enricher for a detail page.

        Args:
            url: The detail page URL to scrape
            platform: Platform type (eventbrite, meetup, linkedin, etc.)
            use_playwright: Whether to use browser automation
        """
        self.url = url
        self.platform = platform.lower()
        self.use_playwright = use_playwright
        self.html = None
        self.soup = None

    def fetch(self, timeout: int = 30) -> bool:
        """
        Fetch the detail page HTML.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_playwright:
                self.html = fetch_html_playwright(
                    self.url, timeout_ms=timeout * 1000, wait_until="networkidle"
                )
            else:
                self.html = fetch_html(
                    self.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
                )

            self.soup = BeautifulSoup(self.html, "lxml")
            return True

        except Exception as e:
            logger.error(f"Failed to fetch detail page {self.url}: {e}")
            return False

    def extract_enrichment_data(self) -> dict[str, Any]:
        """
        Extract additional fields from the detail page.

        Returns:
            Dict with enriched fields (organizer, email, phone, description, etc.)
        """
        if not self.soup:
            logger.warning("No HTML loaded. Call fetch() first.")
            return {}

        # Platform-specific extraction
        if self.platform == "eventbrite":
            return self._extract_eventbrite_details()
        elif self.platform == "meetup":
            return self._extract_meetup_details()
        elif self.platform == "linkedin":
            return self._extract_linkedin_details()
        elif self.platform == "twitter":
            return self._extract_twitter_details()
        else:
            return self._extract_generic_details()

    def _extract_eventbrite_details(self) -> dict[str, Any]:
        """Extract details from Eventbrite event page."""
        data = {}

        # Organizer name
        organizer = self.soup.select_one(
            ".organizer-name, [class*='organizer'] h2, [class*='organizer'] h3, "
            ".event-details__organizer-name"
        )
        if organizer:
            data["company"] = organizer.get_text(strip=True)

        # Event description (full)
        description = self.soup.select_one(
            ".event-description, [class*='description'] [class*='text'], "
            ".structured-content-rich-text"
        )
        if description:
            data["event_description"] = description.get_text(" ", strip=True)[:1000]

        # Organizer profile link
        org_link = self.soup.select_one("a[href*='/o/']")
        if org_link:
            data["organizer_url"] = org_link.get("href", "")

        # Try to find organizer website (rare, but possible)
        website = self.soup.select_one(
            "a[rel='nofollow'][target='_blank'][href^='http']"
        )
        if website:
            href = website.get("href", "")
            if "eventbrite.com" not in href:  # Exclude eventbrite links
                data["website"] = href

        # Date/time (more detailed)
        datetime_elem = self.soup.select_one("[datetime], time[datetime]")
        if datetime_elem:
            data["event_datetime"] = datetime_elem.get("datetime", "")

        # Location (full address)
        location = self.soup.select_one(
            ".event-details__location, [class*='location'] [class*='address'], "
            "[class*='venue-name']"
        )
        if location:
            data["location"] = location.get_text(" ", strip=True)

        return data

    def _extract_meetup_details(self) -> dict[str, Any]:
        """Extract details from Meetup event page."""
        data = {}

        # Group/Organizer name
        group_name = self.soup.select_one(
            "[class*='groupName'], .groupName, [id*='group-name']"
        )
        if group_name:
            data["company"] = group_name.get_text(strip=True)

        # Event description
        description = self.soup.select_one(
            "[class*='description'], .event-description, [class*='eventDescription']"
        )
        if description:
            data["event_description"] = description.get_text(" ", strip=True)[:1000]

        # Group website
        website = self.soup.select_one("a[href*='http'][rel='noopener']")
        if website:
            href = website.get("href", "")
            if "meetup.com" not in href and "facebook.com" not in href:
                data["website"] = href

        # Organizer/Host info
        host = self.soup.select_one("[class*='host'], [class*='organizer']")
        if host:
            data["organizer_name"] = host.get_text(strip=True)

        # Location details
        venue = self.soup.select_one("[class*='venueAddress'], [class*='venue']")
        if venue:
            data["location"] = venue.get_text(" ", strip=True)

        return data

    def _extract_linkedin_details(self) -> dict[str, Any]:
        """Extract details from LinkedIn profile/post."""
        data = {}

        # Profile name
        name = self.soup.select_one(
            ".top-card-layout__title, h1[class*='name'], .pv-text-details__title"
        )
        if name:
            data["full_name"] = name.get_text(strip=True)

        # Company/Title
        headline = self.soup.select_one(
            ".top-card-layout__headline, [class*='headline'], .pv-text-details__subtitle"
        )
        if headline:
            data["company"] = headline.get_text(strip=True)

        # About/Summary
        about = self.soup.select_one(
            ".about-section, [class*='summary'], .pv-about-section"
        )
        if about:
            data["description"] = about.get_text(" ", strip=True)[:1000]

        # Contact info (if visible)
        email = self.soup.select_one("[href^='mailto:']")
        if email:
            data["email"] = email.get("href", "").replace("mailto:", "")

        # Website
        website = self.soup.select_one("a[data-field='website_url']")
        if website:
            data["website"] = website.get("href", "")

        return data

    def _extract_twitter_details(self) -> dict[str, Any]:
        """Extract details from Twitter/X profile."""
        data = {}

        # Profile name
        name = self.soup.select_one("[data-testid='UserName'] span")
        if name:
            data["full_name"] = name.get_text(strip=True)

        # Bio
        bio = self.soup.select_one("[data-testid='UserDescription']")
        if bio:
            data["description"] = bio.get_text(strip=True)

        # Website
        website = self.soup.select_one("a[href*='t.co'][target='_blank']")
        if website:
            # Twitter uses t.co redirects, would need to follow to get real URL
            data["website"] = website.get("href", "")

        # Location
        location = self.soup.select_one("[data-testid='UserLocation']")
        if location:
            data["location"] = location.get_text(strip=True)

        return data

    def _extract_generic_details(self) -> dict[str, Any]:
        """Extract details from generic/unknown platform."""
        data = {}

        # Try to find email addresses in the content
        text = self.soup.get_text()
        import re

        emails = re.findall(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text
        )
        if emails:
            # Take the first email that looks legitimate
            for email in emails:
                if not any(
                    spam in email.lower() for spam in ["noreply", "example", "spam"]
                ):
                    data["email"] = email
                    break

        # Try to find phone numbers
        phones = re.findall(
            r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b", text
        )
        if phones:
            data["phone"] = f"({phones[0][0]}) {phones[0][1]}-{phones[0][2]}"

        # Try to find organizer/company name
        org_keywords = ["organized by", "hosted by", "presented by", "contact:"]
        for keyword in org_keywords:
            if keyword in text.lower():
                idx = text.lower().index(keyword)
                snippet = text[idx : idx + 100]
                # Extract the next line or sentence
                match = re.search(
                    r"(?:by|:)\s*([A-Z][A-Za-z\s&]+?)(?:\.|,|\n|$)", snippet
                )
                if match:
                    data["company"] = match.group(1).strip()
                    break

        # Description (first paragraph or meta description)
        meta_desc = self.soup.select_one("meta[name='description']")
        if meta_desc:
            data["event_description"] = meta_desc.get("content", "")[:500]

        return data


def enrich_prospect(
    prospect_id: int, platform: str = "generic", use_playwright: bool = False
) -> dict[str, Any]:
    """
    Enrich a Prospect by visiting its detail page.

    Args:
        prospect_id: The Prospect ID to enrich
        platform: Platform type for optimized extraction
        use_playwright: Use browser automation if True

    Returns:
        Dict with enrichment results
    """
    from leads.models import Prospect

    try:
        prospect = Prospect.objects.get(id=prospect_id)
    except Prospect.DoesNotExist:
        return {"success": False, "error": f"Prospect {prospect_id} not found"}

    if not prospect.source_url:
        return {"success": False, "error": "No source URL to enrich"}

    # Don't re-enrich if already has contact info
    if prospect.email or prospect.company:
        logger.info(f"Prospect {prospect_id} already has enrichment data, skipping")
        return {"success": True, "skipped": True, "reason": "Already enriched"}

    # Fetch and extract
    enricher = DetailPageEnricher(prospect.source_url, platform, use_playwright)

    if not enricher.fetch():
        return {"success": False, "error": "Failed to fetch detail page"}

    enrichment_data = enricher.extract_enrichment_data()

    if not enrichment_data:
        return {"success": False, "error": "No data extracted from detail page"}

    # Update prospect with enriched data
    updated_fields = []
    for field, value in enrichment_data.items():
        if value and hasattr(prospect, field):
            # Only update if field is currently empty
            current_value = getattr(prospect, field)
            if not current_value or (
                isinstance(current_value, str) and not current_value.strip()
            ):
                setattr(prospect, field, value)
                updated_fields.append(field)

    if updated_fields:
        prospect.save(update_fields=updated_fields + ["updated_at"])

    return {
        "success": True,
        "prospect_id": prospect_id,
        "updated_fields": updated_fields,
        "enrichment_data": enrichment_data,
    }


def enrich_prospects_batch(
    prospect_ids: list[int] = None,
    platform: str = "generic",
    use_playwright: bool = False,
    delay_seconds: float = 2.0,
    max_prospects: int = 50,
) -> dict[str, Any]:
    """
    Enrich multiple prospects in batch.

    Args:
        prospect_ids: List of Prospect IDs (or None for all unenriched)
        platform: Platform type
        use_playwright: Use browser automation
        delay_seconds: Delay between requests (avoid rate limiting)
        max_prospects: Maximum number to enrich in one batch

    Returns:
        Dict with batch results
    """
    from leads.models import Prospect

    # Get prospects to enrich
    if prospect_ids:
        prospects = Prospect.objects.filter(id__in=prospect_ids)
    else:
        # Find unenriched prospects (no email and no company, but has source_url)
        prospects = Prospect.objects.filter(
            source_url__isnull=False, email__isnull=True, company=""
        ).exclude(source_url="")[:max_prospects]

    results = {
        "total": len(prospects),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    for prospect in prospects:
        try:
            result = enrich_prospect(prospect.id, platform, use_playwright)

            if result.get("success"):
                if result.get("skipped"):
                    results["skipped"] += 1
                else:
                    results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "prospect_id": prospect.id,
                        "error": result.get("error", "Unknown error"),
                    }
                )

            # Rate limiting delay
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        except Exception as e:
            logger.exception(f"Error enriching prospect {prospect.id}: {e}")
            results["failed"] += 1
            results["errors"].append({"prospect_id": prospect.id, "error": str(e)})

    return results
