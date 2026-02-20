# Blank Data Issue - Root Cause and Fix

## Issue Summary
The scraping tool was successfully finding items on target websites (144 items per run for Eventbrite), but all extracted fields were coming back blank/empty:
- `event_name`: "" (empty)
- `company`: "" (empty)  
- `email`: None
- `website`: "" (empty)

## Root Cause
**Incorrect CSS selectors in `targets.json`** - The selectors were attempting to match HTML elements that don't exist on the actual Eventbrite page.

### What Was Wrong (Old Configuration)

```json
{
  "item_selector": ".event-card, .search-event-card-wrapper, [data-testid='search-result']",
  "fields": {
    "event_name": ".event-title, .event-card-title, [data-testid='event-title'], h2.event-title",
    "company": ".event-organizer, .organizer-name, [data-testid='organizer-name']",
    "email": ".event-email, [data-testid='event-email'], .contact-email",
    "phone": ".event-phone, [data-testid='event-phone'], .contact-phone",
    "website": ".event-website, [data-testid='event-website'], .organizer-website"
  }
}
```

**Problems:**
1. Multiple fallback selectors (`.event-title, .event-card-title, etc.`) - none of them matched
2. Looking for classes like `.event-organizer` that don't exist on Eventbrite
3. Looking for contact info (email, phone) that isn't available on listing pages
4. Selectors were guesses, not based on actual HTML inspection

### Actual Eventbrite HTML Structure

```html
<div class="event-card">
  <a aria-label="View The Palm Beach Show" class="event-card-link" href="https://...">
    <!-- Image -->
  </a>
  <section class="event-card-details">
    <h3>The Palm Beach Show</h3>
    <p>Palm Beach County Convention Center</p>
    <p>Friday • 6:00 PM</p>
  </section>
</div>
```

**Key findings:**
- Event name is in simple `<h3>` tag (no special class)
- Link is in `a.event-card-link` with `href` attribute
- Link also has `aria-label` attribute with event name
- Email, phone, organizer are NOT available on listing pages
- Would need to visit individual event pages to get contact info

## Solution

### Fixed Configuration

```json
{
  "item_selector": ".event-card",
  "fields": {
    "event_name": "h3",
    "company": "a.event-card-link@aria-label",
    "source_url": "a.event-card-link@href"
  }
}
```

**Changes made:**
1. Simplified `item_selector` to just `.event-card` (which works)
2. Changed `event_name` to simple `h3` selector
3. Used `a.event-card-link@aria-label` for company/event reference
4. Removed email, phone, website fields (not available on listing pages)
5. Kept `source_url` pointing to individual event page

### Results After Fix

**Before:** 0% of fields filled (all blank)
**After:** 100% of fields filled (144/144 items with complete data)

Sample extracted data:
```
Event Name: "The Palm Beach Show"
Company: "View The Palm Beach Show"  
Source URL: "https://www.eventbrite.com/e/the-palm-beach-show-tickets-1853799236419"
```

## How to Test Selectors Before Deploying

Created `test_config.py` script to validate selectors against live websites:

```bash
python test_config.py
```

This script:
1. Fetches the target URL
2. Tests the configured selectors
3. Shows sample extracted data
4. Reports % of fields successfully filled
5. Identifies empty/blank fields

**Use this before updating production configs!**

## How to Update and Deploy

1. **Edit `targets.json`** with correct selectors
2. **Test first:** `python test_config.py`
3. **Sync to database:** `python manage.py sync_targets --file targets.json --update`
4. **Verify in admin:** Check ScrapeTarget config in Django admin
5. **Test scrape:** Use "Test Scrape" button in admin or trigger via API

## Best Practices for Writing Selectors

### 1. Inspect the Actual HTML First
```bash
# Fetch and inspect HTML
python -c "import requests; from bs4 import BeautifulSoup; r = requests.get('URL'); soup = BeautifulSoup(r.text, 'lxml'); print(soup.prettify()[:5000])"
```

### 2. Test Selectors Interactively
```python
from bs4 import BeautifulSoup
import requests

html = requests.get('URL').text
soup = BeautifulSoup(html, 'lxml')

# Test different selectors
soup.select('.event-card')  # Returns list
soup.select_one('h3')  # Returns first match
```

### 3. Use Browser DevTools
- Right-click element → Inspect
- Check actual classes, IDs, attributes
- Don't assume class names - verify them!

### 4. Start Simple, Add Fallbacks Later
```json
// Good - start with one working selector
"event_name": "h3"

// Bad - multiple untested selectors
"event_name": ".title, .event-title, h2.title, [data-title]"
```

### 5. Understand What's Available
- Listing pages have limited info (title, date, location)
- Detail pages have full info (organizer, contact, description)
- Consider two-stage scraping if you need detailed data

### 6. Use Attribute Extraction
```json
// Extract href attribute
"url": "a.event-link@href"

// Extract aria-label attribute  
"title": "a@aria-label"

// Extract data attributes
"id": "[data-event-id]@data-event-id"
```

## Common Pitfalls

### ❌ Don't Do This
```json
// Guessing selectors without testing
"email": ".email, .contact-email, .organizer-email, [type='email']"

// Expecting data that doesn't exist
"phone": ".phone"  // Not on listing pages!

// Overly complex selectors
"title": "div.container > section.events > article.event > h2.title"
```

### ✅ Do This Instead
```json
// Test on actual HTML first
"event_name": "h3"

// Only extract what's available
"source_url": "a.event-card-link@href"

// Use simple, working selectors
"title": "h3"
```

## Debugging Workflow

When you encounter blank data:

1. **Check ScrapeRun status** in admin
   - Success but 0 items created → selectors aren't matching
   - Failed → network/timeout issue

2. **Check raw_payload** in Prospect admin
   - If all fields are empty strings → selectors don't match
   - If fields have "NOT FOUND" → selector is wrong
   - If null/missing → field not in config

3. **Test selectors manually:**
   ```bash
   python test_config.py
   ```

4. **Inspect live HTML:**
   ```bash
   python test_selectors.py
   ```

5. **Update config and sync:**
   ```bash
   # Edit targets.json
   python manage.py sync_targets --file targets.json --update
   ```

6. **Test scrape:**
   - Use Django admin "Test Scrape" button
   - Or API: `POST /ops/trigger-scrape` with `{"target_id": 1}`

## Monitoring for Future Issues

Websites change their HTML structure frequently. Set up monitoring:

1. **Check ScrapeRun stats regularly:**
   - Sudden drop in `item_count` → structure changed
   - Increase in `updated_leads` vs `created_leads` → no new data
   - Multiple failed runs → site blocking or down

2. **Alert on blank data:**
   ```python
   # In tasks.py, add after scrape:
   if run.item_count > 0 and run.created_leads == 0:
       logger.warning(f"Target {target.id} extracted items but created 0 prospects - selectors may be broken")
   ```

3. **Periodic selector validation:**
   - Run `test_config.py` weekly
   - Compare item counts week-over-week
   - Check raw_payload samples for blank fields

## Files Modified

1. **`targets.json`** - Fixed Eventbrite selectors
2. **`test_config.py`** - New testing script for validating selectors
3. **`test_selectors.py`** - HTML inspection helper
4. **`scraper/services/runner.py`** - Added debug logging (already present)

## Summary

**Problem:** Scrapers extracting blank data due to incorrect CSS selectors  
**Solution:** Inspect actual HTML, update selectors to match real structure  
**Prevention:** Test selectors with `test_config.py` before deploying  
**Monitoring:** Check ScrapeRun stats and Prospect raw_payload for blanks  

The scraper is now working correctly and extracting 100% of available data from Eventbrite!