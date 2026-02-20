# Google Sheets Sync Troubleshooting Guide

## Issue: Prospects Not Appearing in Google Sheets

If your prospects are being scraped successfully but not showing up in your Google Sheets "Prospects" tab, follow this guide.

**Important Note:** The system **only syncs Prospects/Leads with meaningful data**. Blank records are filtered out automatically. See [Issue 6](#issue-6-prospects-have-no-data-all-blank) below.

---

## Quick Diagnosis

Run the diagnostic script:
```bash
python diagnose_sheets.py
```

This will check:
- Environment variables
- Google Sheets access
- Spreadsheet permissions
- Sheet tab existence
- Recent prospects
- Celery worker status

---

## Common Issues & Solutions

### Issue 1: "Prospects" Sheet Tab Doesn't Exist

**Symptoms:**
- Error in logs: "Requested entity was not found"
- Error in logs: "Unable to parse range: Prospects!A:Z"

**Solution:**
1. Open your Google Spreadsheet
2. Look at the tabs at the bottom
3. If there's no "Prospects" tab, create one:
   - Click the "+" button to add a new sheet
   - Name it exactly "Prospects" (case-sensitive)
4. Add headers in row 1:
   ```
   A1: Event Name
   B1: Company
   C1: Email
   D1: Phone
   E1: Website
   ```

**Or use existing sheet:**
If you have a sheet with a different name (e.g., "Sheet1"), update your `.env`:
```env
GSHEETS_PROSPECTS_RANGE=Sheet1!A:Z
```

---

### Issue 2: Service Account Doesn't Have Access

**Symptoms:**
- Error: "The caller does not have permission"
- Error: "Requested entity was not found"
- Diagnostic script can't access spreadsheet

**Solution:**
1. Find your service account email in the credentials JSON:
   ```json
   "client_email": "something@project-name.iam.gserviceaccount.com"
   ```

2. Share your Google Spreadsheet with this email:
   - Open your spreadsheet
   - Click "Share" button (top right)
   - Paste the service account email
   - Set permission to "Editor"
   - Uncheck "Notify people"
   - Click "Share"

---

### Issue 3: Wrong Range Configuration

**Symptoms:**
- Prospects appear in wrong columns
- Data is truncated
- Headers get overwritten

**Current Issue:**
Your `.env` has: `GSHEETS_PROSPECTS_RANGE=Prospects!A:Z`

**Problem:** Prospects only have 5 fields (Event Name, Company, Email, Phone, Website) but A:Z is 26 columns.

**Solution:**
Update your `.env` file:
```env
# Change from:
GSHEETS_PROSPECTS_RANGE=Prospects!A:Z

# To:
GSHEETS_PROSPECTS_RANGE=Prospects!A:E
```

**Why:** 
- A:E = 5 columns (perfect for Prospects)
- A:Z = 26 columns (for Leads with full CRM fields)

---

### Issue 4: Celery Worker Not Running

**Symptoms:**
- Manual sync works: `append_prospect_to_sheet(prospect_id)`
- But automatic sync doesn't work
- No errors in Django logs

**Diagnosis:**
```bash
# Check if Celery worker is running
ps aux | grep celery

# Or on Windows PowerShell:
Get-Process | Where-Object {$_.ProcessName -like "*celery*"}
```

**Solution:**
Start the Celery worker:
```bash
# In a new terminal
celery -A leads_app worker -l info
```

Keep this terminal open. You should see:
```
[2026-02-20 12:00:00] celery@hostname ready.
```

---

### Issue 5: GSHEETS_ENABLED is Disabled

**Symptoms:**
- No sync attempts at all
- No errors in logs
- Diagnostic shows "GSHEETS_ENABLED: Not set"

**Solution:**
Add to your `.env` file:
```env
GSHEETS_ENABLED=1
```

Restart Django server and Celery worker.

---

### Issue 6: Prospects Have No Data (All Blank)

**Symptoms:**
- Prospects are created in database
- But all fields are empty/blank
- No rows appear in Sheets (by design - filtered out)

**This is EXPECTED behavior!** The system automatically filters blank prospects.

**Filter Rules:**
- **Prospects:** Only synced if they have `event_name` OR `company` filled
- **Leads:** Only synced if they have `full_name` OR `company` OR `email` filled

**Diagnosis:**
```bash
python manage.py shell --command "from leads.models import Prospect; p = Prospect.objects.order_by('-created_at').first(); print('Event:', p.event_name); print('Company:', p.company)"
```

**If output shows all blank:**
- ✅ System is working correctly (filtering blank records)
- ❌ But your scraper selectors are broken
- 🔧 Fix: See `BLANK_DATA_FIX.md` - Update your CSS selectors

**Check blank rate:**
```bash
python manage.py shell
```
```python
from leads.models import Prospect
blank = Prospect.objects.filter(event_name="", company="").count()
total = Prospect.objects.count()
print(f"Blank: {blank}/{total} ({100*blank/total:.1f}%)")
# If >30% blank, selectors are broken!
```

**See also:** `SHEETS_SYNC_FILTERING.md` for complete filtering documentation

---

### Issue 7: Wrong Spreadsheet ID

**Symptoms:**
- Error: "Requested entity was not found"
- Diagnostic can't access spreadsheet

**Check your GSHEETS_SPREADSHEET_ID:**

It should be one of:
```env
# Option 1: Just the ID
GSHEETS_SPREADSHEET_ID=1jbXGq5kzRZbmDhD-7fG4Y0ae596_uy3tjwAyGqVQCss

# Option 2: Full URL (will be auto-extracted)
GSHEETS_SPREADSHEET_ID=https://docs.google.com/spreadsheets/d/1jbXGq5kzRZbmDhD-7fG4Y0ae596_uy3tjwAyGqVQCss/edit
```

To find your spreadsheet ID:
1. Open your Google Sheet
2. Look at the URL
3. Copy the ID between `/d/` and `/edit`

---

## Complete .env Configuration

Here's the correct configuration for Prospects sync:

```env
# Google Sheets Integration
GSHEETS_ENABLED=1
GSHEETS_SPREADSHEET_ID=YOUR_SPREADSHEET_ID_HERE
GSHEETS_CREDENTIALS_JSON={"type":"service_account",...}

# Prospects Range (5 columns: Event Name, Company, Email, Phone, Website)
GSHEETS_PROSPECTS_RANGE=Prospects!A:E

# Leads Range (24 columns: Full CRM fields) - Optional
GSHEETS_LEADS_RANGE=Leads!A:Z
```

---

## Testing the Fix

### Step 1: Test Manual Sync
```bash
python manage.py shell
```
```python
from sheets_integration.tasks import append_prospect_to_sheet
from leads.models import Prospect

# Get most recent prospect
p = Prospect.objects.order_by('-created_at').first()
print(f"Testing Prospect {p.id}: {p.event_name}")

# Try to sync
append_prospect_to_sheet(p.id)
print("Check your Google Sheet!")
```

### Step 2: Check Google Sheet
1. Open your spreadsheet
2. Go to "Prospects" tab
3. Look for the new row at the bottom
4. It should have: Event Name, Company, Email, Phone, Website

### Step 3: Test Automatic Sync
```bash
# Trigger a scrape
python manage.py shell --command "from scraper.tasks import scrape_target; scrape_target.delay(target_id=2)"

# Wait 30 seconds, then check Google Sheet for new rows
```

---

## Understanding the Sync Flow

```
1. Scraper runs (every 2 hours, automatic)
   ↓
2. Creates Prospects in database
   ↓
3. Validates: Does prospect have event_name OR company?
   ├─ YES → Continue to step 4
   └─ NO → Skip Sheets sync (filtered out)
   ↓
4. Triggers: _enqueue_sheets_sync(prospect_id)
   ↓
5. Queues Celery task: append_prospect_to_sheet.delay(prospect_id)
   ↓
6. Celery Worker executes task
   ↓
7. Converts Prospect to row: [event_name, company, email, phone, website]
   ↓
8. Appends to Google Sheet: Prospects!A:E
```

**If sync isn't working, the break could be at:**
- Step 3: All prospects blank (filtered) - Fix selectors
- Step 4: GSHEETS_ENABLED not set
- Step 5: Celery worker not running
- Step 6-8: Permissions or sheet doesn't exist

---

## Verification Checklist

Use this checklist to verify everything is configured correctly:

- [ ] `.env` has `GSHEETS_ENABLED=1`
- [ ] `.env` has valid `GSHEETS_SPREADSHEET_ID`
- [ ] `.env` has `GSHEETS_CREDENTIALS_JSON` or `GSHEETS_CREDENTIALS_FILE`
- [ ] `.env` has `GSHEETS_PROSPECTS_RANGE=Prospects!A:E` (not A:Z)
- [ ] Google Spreadsheet has a "Prospects" tab
- [ ] Service account email has Editor access to spreadsheet
- [ ] Celery worker is running: `celery -A leads_app worker -l info`
- [ ] Redis is running (required for Celery)
- [ ] Manual sync works: `append_prospect_to_sheet(prospect_id)`
- [ ] Recent prospects have data (not all blank) - Use prospects with event_name or company
- [ ] Understand filtering: Only prospects with data are synced (see `SHEETS_SYNC_FILTERING.md`)

---

## Quick Fixes Summary

### Fix 1: Change Range
```env
# In .env
GSHEETS_PROSPECTS_RANGE=Prospects!A:E
```

### Fix 2: Create Prospects Sheet
1. Open Google Spreadsheet
2. Click "+" to add sheet
3. Name it "Prospects"
4. Add headers: Event Name, Company, Email, Phone, Website

### Fix 3: Share with Service Account
1. Find email in credentials JSON: `"client_email": "..."`
2. Share spreadsheet with that email
3. Set permission to "Editor"

### Fix 4: Start Celery Worker
```bash
celery -A leads_app worker -l info
```

---

## Still Not Working?

### Check Celery Worker Logs
```bash
tail -f celery_worker.log | grep -i "sheets\|prospect"
```

Look for:
- `Task sheets_integration.tasks.append_prospect_to_sheet received`
- `Task sheets_integration.tasks.append_prospect_to_sheet succeeded`
- Or error messages

### Check Django Logs
Look for:
- "Failed to append prospect X to Google Sheets"
- "Sheet 'Prospects' may not exist"
- Permission errors

### Enable Debug Logging
Add to your `.env`:
```env
DJANGO_LOG_LEVEL=DEBUG
```

Restart Django and Celery worker, then check logs.

---

## Common Error Messages

### "Requested entity was not found"
**Cause:** Sheet tab doesn't exist or wrong name
**Fix:** Create "Prospects" tab or update GSHEETS_PROSPECTS_RANGE

### "The caller does not have permission"
**Cause:** Service account not shared with spreadsheet
**Fix:** Share spreadsheet with service account email

### "Unable to parse range"
**Cause:** Invalid range format
**Fix:** Use format: `Prospects!A:E` (sheet name, exclamation, columns)

### No error but no rows appearing
**Cause:** Celery worker not running or tasks not being queued
**Fix:** Start Celery worker, check GSHEETS_ENABLED=1

---

## Testing After Fix

1. **Update .env** with correct configuration
2. **Restart everything:**
   ```bash
   # Stop Django server (Ctrl+C)
   # Stop Celery worker (Ctrl+C)
   
   # Restart
   python manage.py runserver
   celery -A leads_app worker -l info
   ```

3. **Test manual sync:**
   ```bash
   python manage.py shell --command "from sheets_integration.tasks import append_prospect_to_sheet; append_prospect_to_sheet(259)"
   ```

4. **Check Google Sheet** for new row

5. **Trigger automatic scrape:**
   ```bash
   python manage.py shell --command "from scraper.tasks import scrape_target; scrape_target.delay(target_id=2)"
   ```

6. **Wait 1-2 minutes**, then check Google Sheet

---

## Success Criteria

You'll know it's working when:
- ✅ Scraper runs and creates Prospects
- ✅ Celery worker logs show: `Task append_prospect_to_sheet[...] succeeded`
- ✅ Google Sheet "Prospects" tab has new rows
- ✅ Each row has: Event Name, Company, (Email/Phone/Website if available)
- ✅ No errors in Celery worker logs

---

## Need More Help?

- Run diagnostic: `python diagnose_sheets.py`
- Check `HOW_TO_RUN.md` for setup instructions
- Check `TROUBLESHOOTING.md` for general issues
- Check Celery worker logs for specific errors
- Verify all checklist items above are ✓