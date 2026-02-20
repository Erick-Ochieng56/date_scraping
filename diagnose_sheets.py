#!/usr/bin/env python
"""
Diagnostic script for Google Sheets integration issues.

This script helps diagnose why Prospects aren't being synced to Google Sheets.
"""

import os
import sys

import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leads_app.settings")
django.setup()

from leads.models import Prospect
from sheets_integration.tasks import append_prospect_to_sheet


def check_environment_variables():
    """Check if all required environment variables are set."""
    print("=" * 80)
    print("ENVIRONMENT VARIABLES CHECK")
    print("=" * 80)

    required_vars = {
        "GSHEETS_ENABLED": os.getenv("GSHEETS_ENABLED"),
        "GSHEETS_SPREADSHEET_ID": os.getenv("GSHEETS_SPREADSHEET_ID"),
        "GSHEETS_CREDENTIALS_JSON": os.getenv("GSHEETS_CREDENTIALS_JSON"),
        "GSHEETS_CREDENTIALS_FILE": os.getenv("GSHEETS_CREDENTIALS_FILE"),
        "GSHEETS_PROSPECTS_RANGE": os.getenv("GSHEETS_PROSPECTS_RANGE"),
    }

    all_ok = True

    for var_name, value in required_vars.items():
        if var_name in ["GSHEETS_CREDENTIALS_JSON", "GSHEETS_CREDENTIALS_FILE"]:
            # At least one of these should be set
            continue

        if value:
            if var_name == "GSHEETS_CREDENTIALS_JSON":
                print(f"✓ {var_name}: Set (length: {len(value)} chars)")
            elif var_name == "GSHEETS_SPREADSHEET_ID":
                print(f"✓ {var_name}: {value}")
            else:
                print(f"✓ {var_name}: {value}")
        else:
            print(f"✗ {var_name}: NOT SET")
            if var_name not in ["GSHEETS_CREDENTIALS_FILE", "GSHEETS_PROSPECTS_RANGE"]:
                all_ok = False

    # Check credentials
    has_creds_json = bool(required_vars["GSHEETS_CREDENTIALS_JSON"])
    has_creds_file = bool(required_vars["GSHEETS_CREDENTIALS_FILE"])

    print()
    if has_creds_json:
        print("✓ GSHEETS_CREDENTIALS_JSON: Set")
    else:
        print("✗ GSHEETS_CREDENTIALS_JSON: Not set")

    if has_creds_file:
        print(
            f"✓ GSHEETS_CREDENTIALS_FILE: {required_vars['GSHEETS_CREDENTIALS_FILE']}"
        )
    else:
        print("✗ GSHEETS_CREDENTIALS_FILE: Not set")

    if not (has_creds_json or has_creds_file):
        print("\n❌ ERROR: No credentials configured!")
        print("   Set either GSHEETS_CREDENTIALS_JSON or GSHEETS_CREDENTIALS_FILE")
        all_ok = False

    print()
    return all_ok


def check_spreadsheet_access():
    """Test if we can access the Google Spreadsheet."""
    print("=" * 80)
    print("GOOGLE SHEETS ACCESS CHECK")
    print("=" * 80)

    try:
        from sheets_integration.client import get_sheets_service

        print("Attempting to connect to Google Sheets API...")
        service = get_sheets_service()
        print("✓ Successfully created Sheets service")

        # Get spreadsheet ID
        spreadsheet_id = os.getenv("GSHEETS_SPREADSHEET_ID", "")
        if not spreadsheet_id:
            print("✗ No spreadsheet ID configured")
            return False

        # Extract ID if it's a URL
        if "/spreadsheets/d/" in spreadsheet_id:
            parts = spreadsheet_id.split("/spreadsheets/d/")
            if len(parts) > 1:
                spreadsheet_id = parts[1].split("/")[0]

        print(f"Attempting to access spreadsheet: {spreadsheet_id}")

        # Try to get spreadsheet metadata
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        print(
            f"✓ Successfully accessed spreadsheet: {spreadsheet.get('properties', {}).get('title', 'Unknown')}"
        )

        # List available sheets
        sheets = spreadsheet.get("sheets", [])
        print(f"\nAvailable sheet tabs ({len(sheets)}):")
        for sheet in sheets:
            sheet_title = sheet["properties"]["title"]
            print(f"  - {sheet_title}")

        # Check if Prospects sheet exists
        sheet_names = [s["properties"]["title"] for s in sheets]
        prospects_range = os.getenv("GSHEETS_PROSPECTS_RANGE", "Prospects!A:E")
        expected_sheet = (
            prospects_range.split("!")[0] if "!" in prospects_range else "Prospects"
        )

        print(f"\nExpected sheet name: '{expected_sheet}'")
        if expected_sheet in sheet_names:
            print(f"✓ Sheet '{expected_sheet}' exists")
        else:
            print(f"✗ Sheet '{expected_sheet}' NOT FOUND")
            print(f"   Create a sheet tab named '{expected_sheet}' in your spreadsheet")
            print(
                f"   Or update GSHEETS_PROSPECTS_RANGE to use one of the existing sheets"
            )
            return False

        return True

    except Exception as e:
        print(f"✗ ERROR accessing Google Sheets: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_recent_prospects():
    """Check if there are recent prospects in the database."""
    print("\n" + "=" * 80)
    print("RECENT PROSPECTS CHECK")
    print("=" * 80)

    prospects = Prospect.objects.order_by("-created_at")[:10]
    count = prospects.count()

    if count == 0:
        print("No prospects found in database")
        return False

    print(f"Found {count} recent prospects:")
    print()

    for i, prospect in enumerate(prospects, 1):
        print(f"{i}. Prospect ID {prospect.id}:")
        print(f"   Event Name: {prospect.event_name or '(blank)'}")
        print(f"   Company: {prospect.company or '(blank)'}")
        print(f"   Email: {prospect.email or '(blank)'}")
        print(f"   Created: {prospect.created_at}")
        print()

    return True


def test_manual_sync():
    """Test syncing a prospect manually."""
    print("=" * 80)
    print("MANUAL SYNC TEST")
    print("=" * 80)

    # Get most recent prospect
    prospect = Prospect.objects.order_by("-created_at").first()

    if not prospect:
        print("No prospects available to test")
        return False

    print(f"Testing sync for Prospect ID {prospect.id}:")
    print(f"  Event: {prospect.event_name or '(blank)'}")
    print(f"  Company: {prospect.company or '(blank)'}")
    print()

    try:
        from sheets_integration.rows import prospect_to_row

        # Show what would be synced
        row = prospect_to_row(prospect)
        print("Row data to sync:")
        headers = ["Event Name", "Company", "Email", "Phone", "Website"]
        for header, value in zip(headers, row):
            print(f"  {header}: {value or '(empty)'}")
        print()

        # Check if it's blank
        if all(not v or not str(v).strip() for v in row):
            print("⚠️  WARNING: All fields are blank!")
            print("   This prospect has no data to sync")
            print("   Check your scraper selectors - see BLANK_DATA_FIX.md")
            return False

        # Try to sync
        print("Attempting to sync to Google Sheets...")
        append_prospect_to_sheet(prospect.id)
        print("✓ Sync task completed (check Google Sheets to verify)")
        print()
        print("If the row didn't appear in Google Sheets:")
        print("  1. Check that the 'Prospects' sheet tab exists")
        print("  2. Check that the service account has edit access")
        print("  3. Check Celery worker logs for errors")

        return True

    except Exception as e:
        print(f"✗ ERROR during sync test: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_celery_status():
    """Check if Celery is running."""
    print("\n" + "=" * 80)
    print("CELERY STATUS CHECK")
    print("=" * 80)

    try:
        from celery import current_app

        # Try to get worker stats
        inspect = current_app.control.inspect()
        stats = inspect.stats()

        if stats:
            print(f"✓ Celery workers running: {len(stats)}")
            for worker_name in stats.keys():
                print(f"  - {worker_name}")
        else:
            print("⚠️  WARNING: No Celery workers detected")
            print("   Start workers with: celery -A leads_app worker -l info")
            return False

        return True

    except Exception as e:
        print(f"⚠️  Could not check Celery status: {e}")
        print("   Make sure Celery worker is running")
        return False


def main():
    print("\n" + "=" * 80)
    print("GOOGLE SHEETS PROSPECTS SYNC DIAGNOSTIC")
    print("=" * 80)
    print()

    results = {}

    # Run all checks
    results["env_vars"] = check_environment_variables()
    print()

    results["spreadsheet"] = check_spreadsheet_access()
    print()

    results["prospects"] = check_recent_prospects()
    print()

    results["celery"] = check_celery_status()
    print()

    # Only test sync if everything else looks good
    if all([results["env_vars"], results["spreadsheet"], results["prospects"]]):
        results["sync"] = test_manual_sync()
    else:
        print("=" * 80)
        print("SKIPPING SYNC TEST - Fix issues above first")
        print("=" * 80)
        results["sync"] = False

    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)

    all_passed = all(results.values())

    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {check_name.replace('_', ' ').title()}")

    print()

    if all_passed:
        print("✅ All checks passed!")
        print()
        print("If prospects still aren't appearing in Google Sheets:")
        print("  1. Check that new prospects are being created (scraper is running)")
        print("  2. Check Celery worker logs: tail -f celery_worker.log")
        print("  3. Verify the service account has edit permissions on the spreadsheet")
        print("  4. Try running: python manage.py shell")
        print("     >>> from sheets_integration.tasks import append_prospect_to_sheet")
        print("     >>> append_prospect_to_sheet(PROSPECT_ID)")
    else:
        print("❌ Some checks failed. Fix the issues above.")
        print()
        print("Common issues:")
        print("  - Missing GSHEETS_SPREADSHEET_ID in .env")
        print("  - Missing GSHEETS_CREDENTIALS_JSON or GSHEETS_CREDENTIALS_FILE")
        print("  - Service account not shared with spreadsheet")
        print("  - 'Prospects' sheet tab doesn't exist")
        print("  - Celery worker not running")
        print("  - All prospect fields are blank (scraper issue)")

    print()


if __name__ == "__main__":
    main()
