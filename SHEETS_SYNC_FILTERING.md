# Google Sheets Sync - Filtering for Successful Data Only

## Overview

The system now **only syncs Prospects and Leads with meaningful data** to Google Sheets. This prevents cluttering your sheets with blank or incomplete records from failed scraping attempts.

---

## How It Works

### For Prospects (Stage 1 Scraping)

**Validation Rules:**
A Prospect is considered "successful" and synced to Sheets if it has:
- **Event Name** (filled) OR
- **Company** (filled)

**What gets synced:**
```
✓ Event Name: "Tech Conference 2026", Company: "" → SYNCED
✓ Event Name: "", Company: "Acme Corp" → SYNCED
✓ Event Name: "Tech Meetup", Company: "Tech Group" → SYNCED
✗ Event Name: "", Company: "" → SKIPPED (blank)
✗ Event Name: "   ", Company: "  " → SKIPPED (whitespace only)
```

### For Leads (Stage 2 Conversion)

**Validation Rules:**
A Lead is considered "successful" and synced to Sheets if it has at least one of:
- **Full Name** (filled) OR
- **Company** (filled) OR
- **Email** (filled)

**What gets synced:**
```
✓ Name: "John Doe", Company: "", Email: "" → SYNCED
✓ Name: "", Company: "Tech Corp", Email: "" → SYNCED
✓ Name: "", Company: "", Email: "john@example.com" → SYNCED
✓ Name: "Jane", Company: "Acme", Email: "jane@acme.com" → SYNCED
✗ Name: "", Company: "", Email: "" → SKIPPED (all blank)
```

---

## Implementation Details

### Prospect Sync Filter

**Location:** `scraper/tasks.py`

**Function:** `_is_prospect_successful(prospect)`

```python
def _is_prospect_successful(prospect) -> bool:
    """
    Check if a prospect has meaningful data worth syncing to Google Sheets.
    Returns True if prospect has at least event_name OR company filled.
    """
    has_event = prospect.event_name and str(prospect.event_name).strip()
    has_company = prospect.company and str(prospect.company).strip()
    return has_event or has_company
```

**Called by:** `_enqueue_sheets_sync()` during scraping

### Lead Sync Filter

**Location:** `leads/models.py`

**Method:** `Prospect._sync_lead_to_sheets(lead)`

```python
def _sync_lead_to_sheets(self, lead: "Lead") -> None:
    """
    Sync a successful Lead to Google Sheets.
    Only syncs if Lead has meaningful data (not all blank fields).
    """
    has_name = lead.full_name and str(lead.full_name).strip()
    has_company = lead.company and str(lead.company).strip()
    has_email = lead.email and str(lead.email).strip()
    
    # Need at least one of: name, company, or email
    if not (has_name or has_company or has_email):
        return  # Skip sync
```

**Called by:** `Prospect.convert_to_lead()` when converting to Lead

---

## Why This Matters

### Before Filtering (The Problem)

```
Google Sheet "Prospects" tab:
| Event Name | Company | Email | Phone | Website |
|------------|---------|-------|-------|---------|
|            |         |       |       |         |  ← Blank row
| Tech Conf  | Acme    |       |       |         |  ← Good data
|            |         |       |       |         |  ← Blank row
|            |         |       |       |         |  ← Blank row
| Meetup     |         |       |       |         |  ← Good data
```

**Issues:**
- ❌ Cluttered with blank rows
- ❌ Hard to review/analyze
- ❌ Wastes quota/API calls
- ❌ Looks unprofessional

### After Filtering (The Solution)

```
Google Sheet "Prospects" tab:
| Event Name | Company | Email | Phone | Website |
|------------|---------|-------|-------|---------|
| Tech Conf  | Acme    |       |       |         |  ← Only good data
| Meetup     |         |       |       |         |  ← Only good data
```

**Benefits:**
- ✅ Clean, readable sheets
- ✅ Only actionable prospects
- ✅ Saves API calls
- ✅ Better for team review

---

## What Happens to Filtered Records?

**Filtered Prospects/Leads are:**
- ✅ Still created in the database
- ✅ Visible in Django Admin
- ✅ Available for debugging
- ✅ Counted in scrape statistics
- ❌ NOT synced to Google Sheets

**Why keep them in DB?**
- Audit trail of scraping activity
- Identify broken selectors (many blank records = scraper issue)
- Debug and troubleshooting
- Statistics and reporting

---

## Logging

The system logs when records are filtered:

**Prospect Filtering:**
```
[DEBUG] Skipping Sheets sync for Prospect 123: no meaningful data 
        (event_name='', company='')
```

**Lead Filtering:**
```
[DEBUG] Skipping Sheets sync for Lead 456: no meaningful data 
        (name='', company='', email='')
```

**Successful Sync:**
```
[DEBUG] Queued Sheets sync for Prospect 123
```

**To see debug logs:**
```bash
# Set in .env
DJANGO_LOG_LEVEL=DEBUG

# Or check Celery worker logs
tail -f celery_worker.log | grep -i "sheets sync"
```

---

## Monitoring Blank Data

### Check Filtered Prospects

```bash
python manage.py shell
```

```python
from leads.models import Prospect

# Find prospects that would be filtered
blank_prospects = Prospect.objects.filter(
    event_name="", 
    company=""
)

print(f"Total blank prospects: {blank_prospects.count()}")

# Check if this is a lot (indicates scraper issues)
total_prospects = Prospect.objects.count()
blank_percentage = (blank_prospects.count() / total_prospects * 100) if total_prospects > 0 else 0

print(f"Blank percentage: {blank_percentage:.1f}%")

if blank_percentage > 20:
    print("⚠️  WARNING: High blank rate - check your scraper selectors!")
```

### Expected Rates

**Healthy scraping:**
- ✅ 0-10% blank prospects = Normal (some sites have structure variations)
- ⚠️ 10-30% blank prospects = Check selectors, may need updates
- ❌ 30%+ blank prospects = Scraper is broken, fix selectors immediately

**If you see high blank rates:**
1. Run: `python test_config.py` to test selectors
2. Check: `BLANK_DATA_FIX.md` for selector troubleshooting
3. Update: `targets.json` with correct selectors
4. Sync: `python manage.py sync_targets --update`

---

## Customizing Filter Rules

### Change Prospect Filter

Edit `scraper/tasks.py`:

```python
def _is_prospect_successful(prospect) -> bool:
    """Customize validation rules here."""
    
    # Option 1: Require BOTH event_name AND company (stricter)
    has_event = prospect.event_name and str(prospect.event_name).strip()
    has_company = prospect.company and str(prospect.company).strip()
    return has_event and has_company  # Both required
    
    # Option 2: Require event_name only
    return prospect.event_name and str(prospect.event_name).strip()
    
    # Option 3: Require ANY non-empty field (lenient)
    return any([
        prospect.event_name and str(prospect.event_name).strip(),
        prospect.company and str(prospect.company).strip(),
        prospect.email and str(prospect.email).strip(),
        prospect.website and str(prospect.website).strip(),
    ])
```

### Change Lead Filter

Edit `leads/models.py`:

```python
def _sync_lead_to_sheets(self, lead: "Lead") -> None:
    """Customize validation rules here."""
    
    # Option 1: Require email (stricter)
    if not (lead.email and str(lead.email).strip()):
        return
    
    # Option 2: Require name AND (email OR company)
    has_name = lead.full_name and str(lead.full_name).strip()
    has_email = lead.email and str(lead.email).strip()
    has_company = lead.company and str(lead.company).strip()
    
    if not (has_name and (has_email or has_company)):
        return
```

**After changes:**
1. Restart Django server
2. Restart Celery worker

---

## FAQ

### Q: Can I sync ALL prospects, even blank ones?

**Answer:** Yes, modify the filter function:

```python
# In scraper/tasks.py
def _is_prospect_successful(prospect) -> bool:
    return True  # Sync everything
```

**Not recommended** - you'll get many blank rows cluttering your sheet.

### Q: What if I want to see blank prospects for debugging?

**Answer:** They're still in the database! View them in:
- Django Admin: `http://localhost:8000/admin/leads/prospect/`
- Filter by empty fields to see blank prospects

### Q: How do I know if filtering is working?

**Answer:** Check the logs:

```bash
# Look for "Skipping Sheets sync" messages
tail -f celery_worker.log | grep "Skipping Sheets sync"

# Count how many are filtered
grep "Skipping Sheets sync" celery_worker.log | wc -l
```

### Q: What counts as "meaningful data"?

**Answer:**
- **For Prospects:** At minimum, event_name OR company must be filled
- **For Leads:** At minimum, full_name OR company OR email must be filled

This ensures every row in Sheets has at least one piece of useful information.

### Q: Will this affect my scrape statistics?

**Answer:** No! Statistics still count ALL prospects:
- `created_leads` = All prospects created (including filtered)
- `updated_leads` = All prospects updated (including filtered)

Only Sheets sync is filtered, not database creation.

---

## Testing the Filter

### Test Prospect Filtering

```python
from leads.models import Prospect
from scraper.tasks import _is_prospect_successful

# Create test prospects
p1 = Prospect(event_name="Tech Conf", company="")
p2 = Prospect(event_name="", company="Acme Corp")
p3 = Prospect(event_name="", company="")

# Test filter
print(f"P1 (has event): {_is_prospect_successful(p1)}")  # True
print(f"P2 (has company): {_is_prospect_successful(p2)}")  # True
print(f"P3 (blank): {_is_prospect_successful(p3)}")  # False
```

### Test Lead Filtering

```python
from leads.models import Lead

# Create test lead
lead = Lead(
    full_name="",
    company="",
    email=""
)

# Check if it would be synced
has_name = lead.full_name and str(lead.full_name).strip()
has_company = lead.company and str(lead.company).strip()
has_email = lead.email and str(lead.email).strip()

would_sync = has_name or has_company or has_email
print(f"Would sync: {would_sync}")  # False
```

---

## Summary

✅ **Only successful Prospects/Leads sync to Google Sheets**

**Prospect Filter:**
- Must have: event_name OR company

**Lead Filter:**
- Must have: full_name OR company OR email

**Benefits:**
- Clean, actionable data in Sheets
- No blank rows cluttering your workspace
- Saves API calls
- Better team experience

**Blank records:**
- Still stored in database
- Visible in Django Admin
- Used for debugging/statistics
- Not synced to Sheets

**To monitor:**
- Check logs for "Skipping Sheets sync" messages
- High blank rate = scraper selectors need fixing
- Run `python test_config.py` to validate selectors