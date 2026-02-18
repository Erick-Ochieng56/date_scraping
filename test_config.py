#!/usr/bin/env python
"""
Test script to validate scraper selectors against live Eventbrite page.
This helps debug blank data issues by testing selectors before running full scrape.
"""

import os
import sys

import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leads_app.settings")
django.setup()

from scraper.services.extract import extract_items
from scraper.services.fetch import fetch_html


def test_eventbrite_selectors():
    """Test the Eventbrite selector configuration."""

    url = "https://www.eventbrite.com/d/united-states/tech/events/"

    # Current configuration
    config = {
        "item_selector": ".event-card",
        "fields": {
            "event_name": "h3",
            "company": "a.event-card-link@aria-label",
            "source_url": "a.event-card-link@href",
        },
    }

    print("=" * 80)
    print("TESTING EVENTBRITE SELECTORS")
    print("=" * 80)
    print(f"\nFetching: {url}")
    print(f"Item selector: {config['item_selector']}")
    print(f"Fields: {list(config['fields'].keys())}")
    print()

    try:
        # Fetch HTML
        html = fetch_html(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        print(f"✓ HTML fetched successfully ({len(html)} bytes)")

        # Extract items
        items = extract_items(
            html, item_selector=config["item_selector"], fields=config["fields"]
        )

        print(f"✓ Extracted {len(items)} items")
        print()

        if not items:
            print("❌ ERROR: No items extracted! Check item_selector.")
            return False

        # Check first 3 items
        print("=" * 80)
        print("SAMPLE EXTRACTED DATA (first 3 items)")
        print("=" * 80)

        all_empty = True
        for i, item in enumerate(items[:3], 1):
            print(f"\nItem {i}:")
            for key, value in item.items():
                if not key.startswith("_"):
                    is_empty = not value or str(value).strip() == ""
                    status = "❌ EMPTY" if is_empty else "✓"
                    print(f"  {status} {key}: {repr(value)[:100]}")
                    if value and str(value).strip():
                        all_empty = False

        print()
        print("=" * 80)

        if all_empty:
            print("❌ RESULT: All fields are EMPTY - selectors are NOT working!")
            print("\nTroubleshooting:")
            print("1. Check if website structure has changed")
            print("2. Try fetching the page manually and inspect HTML")
            print("3. Website may require JavaScript (use target_type: 'playwright')")
            return False
        else:
            print("✓ RESULT: Selectors are working! Data is being extracted.")

            # Count empty vs filled
            total_fields = len(items) * len([k for k in config["fields"].keys()])
            empty_count = sum(
                1
                for item in items
                for k, v in item.items()
                if not k.startswith("_") and (not v or str(v).strip() == "")
            )
            filled_count = total_fields - empty_count

            print(f"\nStatistics:")
            print(f"  Total items: {len(items)}")
            print(f"  Fields per item: {len(config['fields'])}")
            print(
                f"  Filled fields: {filled_count}/{total_fields} ({100 * filled_count // total_fields}%)"
            )
            print(
                f"  Empty fields: {empty_count}/{total_fields} ({100 * empty_count // total_fields}%)"
            )

            return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_meetup_selectors():
    """Test the Meetup selector configuration (requires Playwright)."""

    url = "https://www.meetup.com/find/events/"

    config = {
        "item_selector": ".eventCard, [data-testid='event-card'], .event-listing",
        "fields": {
            "full_name": ".eventCard-title, [data-testid='event-title'], .event-title",
            "event_date": ".eventCard-date, [data-testid='event-date'], .event-date",
            "event_name": ".eventCard-description, .event-description",
            "source_url": "a.eventCard-link@href, a[data-testid='event-link']@href",
        },
    }

    print("\n" + "=" * 80)
    print("TESTING MEETUP SELECTORS (Playwright required)")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Note: Meetup requires JavaScript, so this test needs Playwright.")
    print(f"If you see timeouts, this is expected on slow connections.")
    print()

    try:
        from scraper.services.fetch import fetch_html_playwright

        print("Fetching with Playwright (this may take 30-45 seconds)...")
        html = fetch_html_playwright(url, timeout_ms=45000, wait_until="networkidle")
        print(f"✓ HTML fetched successfully ({len(html)} bytes)")

        items = extract_items(
            html, item_selector=config["item_selector"], fields=config["fields"]
        )

        print(f"✓ Extracted {len(items)} items")

        if items:
            print("\nFirst item sample:")
            for key, value in list(items[0].items())[:5]:
                print(f"  {key}: {repr(value)[:80]}")

        return len(items) > 0

    except TimeoutError as e:
        print(f"⚠ TIMEOUT: {e}")
        print(
            "This is common for Meetup. The site may be slow or blocking automated access."
        )
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SCRAPER CONFIGURATION TEST")
    print("=" * 80)
    print("\nThis script tests your scraper selectors against live websites")
    print("to help diagnose blank data issues.")
    print()

    # Test Eventbrite
    eventbrite_ok = test_eventbrite_selectors()

    # Test Meetup (optional, slower)
    print("\n")
    test_meetup = (
        input("Test Meetup selectors too? (takes 30-45s) [y/N]: ").strip().lower()
    )
    if test_meetup in ["y", "yes"]:
        meetup_ok = test_meetup_selectors()
    else:
        meetup_ok = None
        print("Skipping Meetup test.")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    if eventbrite_ok:
        print("✓ Eventbrite: WORKING")
    else:
        print("❌ Eventbrite: FAILED (needs fixing)")

    if meetup_ok is True:
        print("✓ Meetup: WORKING")
    elif meetup_ok is False:
        print("❌ Meetup: FAILED (needs fixing)")
    else:
        print("⊘ Meetup: NOT TESTED")

    print()
    print("Next steps:")
    if not eventbrite_ok:
        print("1. Update selectors in targets.json for Eventbrite")
        print("2. Run this test again to verify")
    else:
        print("1. Your selectors look good!")
        print(
            "2. Sync targets: python manage.py sync_targets --file targets.json --update"
        )
        print("3. Trigger a test scrape from Django admin or via API")
