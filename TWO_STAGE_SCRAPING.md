# Two-Stage Scraping System - Complete Data Collection

## Overview

The two-stage scraping system allows you to collect complete data including contact information by:

1. **Stage 1 (Listing Pages)** - Fast discovery of events/profiles → Basic info + URLs
2. **Stage 2 (Detail Pages)** - Slow enrichment → Contact info, full descriptions, organizer details

This approach balances speed with data completeness, allowing you to discover hundreds of leads quickly, then selectively enrich the most promising ones.

---

## Why Two-Stage Scraping?

### The Problem

Most event platforms (Eventbrite, Meetup) and social platforms (LinkedIn, Twitter) don't show contact information on listing pages:

- **Listing pages** show: Event name, date, location, URL
- **Detail pages** show: Full description, organizer info, sometimes contact details
- **Contact info** (email, phone) is usually hidden or requires authentication

### The Solution

**Stage 1:** Scrape listing pages to build a prospect pipeline (fast, bulk)
**Stage 2:** Visit detail pages to enrich prospects with additional data (slow, selective)

### When to Use Each Stage

| Use Case | Stage 1 Only | Stage 1 + Stage 2 |
|----------|--------------|-------------------|
| Bulk event discovery | ✅ | |
| Building prospect pipeline | ✅ | |
| Need contact info | | ✅ |
| Qualifying leads | | ✅ |
| Time-sensitive scraping | ✅ | |
| Deep research | | ✅ |

---

## Architecture

### Stage 1: Listing Page Scraping (Already Implemented)

```
Listing Page → Extract Items → Create Prospects
     ↓              ↓                 ↓
Multiple events  Basic fields:   Stored in DB
per page        - Event name     with source_url
                - Source URL
                - Date/location
```

**Speed:** 1-2 seconds per page (50-100 events/page)
**Data:** Basic information only
**Automation:** Runs every 2 hours via Celery Beat

### Stage 2: Detail Page Enrichment (New)

```
Prospect → Visit Detail Page → Extract Additional Fields → Update Prospect
   ↓              ↓                       ↓                        ↓
Has URL    Fetch full HTML        - Organizer name        Enriched data
                                  - Contact info           stored in DB
                                  - Full description
```

**Speed:** 1-5 seconds per prospect
**Data:** Complete information (if available)
**Automation:** Manual or automatic (configurable)

---

## Setup & Configuration

### Environment Variables

Add to your `.env` file:

```env
# Enable automatic enrichment (Stage 2)
ENRICHMENT_ENABLED=1

# How often to run enrichment (seconds, default: 1800 = 30 minutes)
ENRICHMENT_INTERVAL_SECONDS=1800

# Maximum prospects to enrich per batch (default: 25)
ENRICHMENT_BATCH_SIZE=25

# Delay between detail page requests (seconds, default: 2)
ENRICHMENT_DELAY=2.0

# Use Playwright for JS-heavy sites like LinkedIn (default: false)
ENRICHMENT_USE_PLAYWRIGHT=0
```

### Platform-Specific Settings

Different platforms need different approaches:

```env
# For Eventbrite (HTML scraping is fine)
ENRICHMENT_USE_PLAYWRIGHT=0

# For Meetup, LinkedIn, Twitter (needs JavaScript)
ENRICHMENT_USE_PLAYWRIGHT=1
```

---

## Usage

### Option 1: Manual Enrichment (Command Line)

#### Basic Usage
```bash
# Enrich unenriched prospects (no email and no company)
python manage.py enrich_prospects

# Enrich specific prospects
python manage.py enrich_prospects --prospect-ids 123 124 125

# Enrich Eventbrite prospects
python manage.py enrich_prospects --platform eventbrite --max-prospects 50

# Enrich with Playwright (for JS-heavy sites)
python manage.py enrich_prospects --platform linkedin --use-playwright
```

#### Advanced Options
```bash
# Dry run (preview without changes)
python manage.py enrich_prospects --dry-run

# Filter by source
python manage.py enrich_prospects --source "Eventbrite"

# Queue in Celery (async)
python manage.py enrich_prospects --async

# Custom delay between requests
python manage.py enrich_prospects --delay 5.0

# Filter only prospects with no contact info
python manage.py enrich_prospects --filter no-contact --max-prospects 100
```

#### Filter Options
- `--filter unenriched` - No email AND no company (default)
- `--filter no-contact` - No email (may have company)
- `--filter all` - All prospects with URLs

### Option 2: Automatic Enrichment (Celery)

#### Enable Automatic Enrichment

1. **Set environment variables:**
```bash
ENRICHMENT_ENABLED=1
ENRICHMENT_BATCH_SIZE=25
ENRICHMENT_INTERVAL_SECONDS=1800  # Every 30 minutes
```

2. **Restart Celery Beat:**
```bash
celery -A leads_app beat -l info
```

3. **Monitor logs:**
```
[2026-02-16 12:00:00] Celery beat: auto-enrich-prospects task scheduled
[2026-02-16 12:00:05] Task scraper.tasks.auto_enrich_new_prospects started
[2026-02-16 12:05:30] Auto-enrichment completed: 20 enriched, 3 failed, 2 skipped
```

#### How Automatic Enrichment Works

```
Every 30 minutes:
  1. Find prospects with source_url but no email/company
  2. Visit their detail pages (up to 25 per run)
  3. Extract additional fields
  4. Update prospects with enriched data
  5. Wait 2 seconds between requests (rate limiting)
```

### Option 3: API Trigger (Programmatic)

```python
from scraper.tasks import enrich_prospect_detail, enrich_prospects_batch_task

# Enrich single prospect
result = enrich_prospect_detail.delay(prospect_id=123, platform="eventbrite")

# Enrich batch
result = enrich_prospects_batch_task.delay(
    prospect_ids=[123, 124, 125],
    platform="eventbrite",
    use_playwright=False,
    delay_seconds=2.0,
)
```

---

## What Data Gets Enriched?

### Eventbrite Detail Pages

```json
{
  "company": "Event Organizer Name",
  "event_description": "Full event description (first 1000 chars)",
  "organizer_url": "https://www.eventbrite.com/o/organizer-123",
  "website": "https://organizer-website.com",
  "event_datetime": "2026-03-15T18:00:00",
  "location": "Full venue address"
}
```

**Availability:** ✅ Organizer name, ⚠️ Website (sometimes), ❌ Email (rare)

### Meetup Detail Pages

```json
{
  "company": "Meetup Group Name",
  "event_description": "Full event description",
  "website": "Group website URL (if provided)",
  "organizer_name": "Host name",
  "location": "Full venue address"
}
```

**Availability:** ✅ Group name, ⚠️ Website (sometimes), ❌ Email (rare)

### LinkedIn Profiles

```json
{
  "full_name": "John Doe",
  "company": "Senior Engineer at Tech Corp",
  "description": "About section / summary",
  "email": "john@example.com (if visible)",
  "website": "Personal website URL"
}
```

**Availability:** ✅ Name/company, ⚠️ Email (requires authentication), ⚠️ Website (if in profile)

**Note:** LinkedIn heavily restricts scraping and requires authentication. Consider using LinkedIn API or Sales Navigator instead.

### Twitter/X Profiles

```json
{
  "full_name": "Display name",
  "description": "Bio text",
  "website": "Profile website URL",
  "location": "Location text"
}
```

**Availability:** ✅ Name/bio, ⚠️ Website (if in bio), ❌ Email (not shown)

### Generic Sites

```json
{
  "email": "contact@example.com (if found in page text)",
  "phone": "(555) 123-4567 (if found in page text)",
  "company": "Organizer name (if detected)",
  "event_description": "Meta description or first paragraph"
}
```

**Availability:** ⚠️ Varies greatly by site

---

## Monitoring & Debugging

### Check Enrichment Status

```bash
# View recent prospects and enrichment status
python manage.py shell --command "
from leads.models import Prospect;
prospects = Prospect.objects.order_by('-updated_at')[:10];
for p in prospects:
    print(f'ID {p.id}: {p.event_name or \"(no name)\"}');
    print(f'  Company: {p.company or \"(not enriched)\"}');
    print(f'  Email: {p.email or \"(not enriched)\"}');
    print(f'  URL: {p.source_url[:60]}...');
    print()
"
```

### Check Celery Logs

```bash
# Watch Celery worker logs for enrichment tasks
tail -f celery_worker.log | grep -i "enrich"
```

### Common Log Messages

```
✓ Success:
  "Enriched prospect 123: updated ['company', 'event_description'] fields"

⊘ Skipped:
  "Prospect 123 already has enrichment data, skipping"

✗ Failed:
  "Failed to enrich prospect 123: No source URL to enrich"
  "Failed to enrich prospect 123: Failed to fetch detail page"
```

---

## Best Practices

### 1. Rate Limiting

**Always use delays** to avoid getting blocked:

```bash
# Good: 2-5 seconds between requests
python manage.py enrich_prospects --delay 2.0

# Bad: No delay = high risk of blocking
python manage.py enrich_prospects --delay 0
```

**Recommended delays by platform:**
- Eventbrite: 2 seconds
- Meetup: 3 seconds
- LinkedIn: 5 seconds (high risk)
- Generic sites: 2-3 seconds

### 2. Batch Size

**Don't enrich all prospects at once:**

```bash
# Good: Process in small batches
python manage.py enrich_prospects --max-prospects 25

# Bad: Large batch = long runtime, higher risk
python manage.py enrich_prospects --max-prospects 1000
```

### 3. Selective Enrichment

**Enrich only promising prospects:**

```bash
# Filter by source
python manage.py enrich_prospects --source "Eventbrite - Tech Events"

# Enrich specific high-value prospects
python manage.py enrich_prospects --prospect-ids 100 101 102
```

### 4. Use Dry Run First

**Test before running:**

```bash
# See what would be enriched
python manage.py enrich_prospects --dry-run

# Then run for real
python manage.py enrich_prospects
```

### 5. Monitor for Blocking

**Signs you're being blocked:**
- Many "Failed to fetch detail page" errors
- Timeouts or connection errors
- 403 Forbidden responses
- CAPTCHAs appearing

**Solutions:**
- Increase delay between requests
- Reduce batch size
- Use proxies (advanced)
- Rotate user agents
- Respect robots.txt

---

## Limitations & Caveats

### Email/Phone Availability

**Reality check:** Most platforms don't show contact info publicly.

| Platform | Email | Phone | Workaround |
|----------|-------|-------|------------|
| Eventbrite | ❌ | ❌ | Register for event, message through platform |
| Meetup | ❌ | ❌ | Join group, message through platform |
| LinkedIn | ⚠️ | ❌ | Requires connection/InMail |
| Twitter | ❌ | ❌ | Check bio for link to website |
| Generic | ⚠️ | ⚠️ | Some sites have contact pages |

**Recommendation:** Use enrichment for discovery and qualification, then:
1. Visit event pages manually
2. Use platform messaging
3. Check organizer websites
4. Use paid enrichment APIs (Hunter.io, Apollo.io)

### Anti-Scraping Measures

**Many sites actively block scrapers:**

- Rate limiting (429 errors)
- IP bans
- JavaScript challenges
- CAPTCHAs
- Login requirements

**Best approach:**
- Use this tool for **initial discovery** (Stage 1)
- Do **manual research** for high-value leads
- Consider **paid APIs** for bulk enrichment

### LinkedIn Specifics

**LinkedIn is difficult to scrape:**
- Requires authentication
- Aggressive bot detection
- Terms of Service prohibit scraping
- High risk of account ban

**Better alternatives:**
- LinkedIn API (official, paid)
- LinkedIn Sales Navigator
- Manual research
- Third-party enrichment services

---

## Workflow Examples

### Example 1: Quick Discovery + Manual Research

```bash
# Stage 1: Scrape listing pages (automatic, every 2 hours)
# Result: 500 prospects discovered

# Review in Google Sheets
# → Identify 50 promising prospects

# Manual research:
# → Visit their event pages
# → Check organizer websites
# → Add contact info manually

# Convert to Leads when ready
```

### Example 2: Automated Discovery + Selective Enrichment

```bash
# Stage 1: Scrape listing pages (automatic)
# Result: 500 prospects

# Filter in Django Admin by event type/location
# → Identify 100 promising prospects

# Stage 2: Enrich selected prospects
python manage.py enrich_prospects --prospect-ids 1 2 3 ... 100 --platform eventbrite

# Review enriched data in Google Sheets
# → Convert 20 qualified prospects to Leads
```

### Example 3: Fully Automated Pipeline

```bash
# .env configuration:
ENRICHMENT_ENABLED=1
ENRICHMENT_BATCH_SIZE=25
ENRICHMENT_INTERVAL_SECONDS=1800

# System runs automatically:
# 1. Every 2 hours: Scrape listings → Create Prospects
# 2. Every 30 minutes: Enrich 25 unenriched Prospects
# 3. Sync to Google Sheets continuously
# 4. Team reviews and converts to Leads manually
```

---

## Troubleshooting

### Issue: No data extracted from detail pages

**Symptoms:**
- Enrichment completes but no fields updated
- Empty values for company, email, etc.

**Solutions:**
```bash
# 1. Check if platform detection is correct
python manage.py shell --command "
from scraper.services.enrichment import DetailPageEnricher;
enricher = DetailPageEnricher('https://...', 'eventbrite');
print(f'Platform: {enricher.platform}');
"

# 2. Test selectors manually
python manage.py shell --command "
from scraper.services.enrichment import DetailPageEnricher;
enricher = DetailPageEnricher('https://...', 'eventbrite');
enricher.fetch();
data = enricher.extract_enrichment_data();
print(data);
"

# 3. Try different platform setting
python manage.py enrich_prospects --platform generic
```

### Issue: "Failed to fetch detail page"

**Causes:**
- URL is invalid or broken
- Site is blocking requests
- Network/DNS issues
- Timeout (page too slow)

**Solutions:**
```bash
# Increase timeout (edit enrichment.py)
# Use Playwright for JS sites
python manage.py enrich_prospects --use-playwright

# Test URL manually in browser
# Check network connectivity
```

### Issue: Getting rate limited / blocked

**Symptoms:**
- 429 errors
- Connection refused
- Many timeouts

**Solutions:**
```bash
# Increase delay
python manage.py enrich_prospects --delay 5.0

# Reduce batch size
python manage.py enrich_prospects --max-prospects 10

# Use Playwright (looks more like real browser)
python manage.py enrich_prospects --use-playwright
```

### Issue: Enrichment taking too long

**Causes:**
- Large batch size
- Slow detail pages
- Short delays accumulating

**Solutions:**
```bash
# Reduce batch size
python manage.py enrich_prospects --max-prospects 25

# Reduce delay (carefully!)
python manage.py enrich_prospects --delay 1.0

# Use async mode
python manage.py enrich_prospects --async

# Schedule during off-hours
# Set ENRICHMENT_INTERVAL_SECONDS to run overnight
```

---

## Performance Benchmarks

### Stage 1 (Listing Pages)
- **Speed:** 1-2 seconds per page
- **Throughput:** 50-100 prospects/page
- **Total:** 2500-5000 prospects/hour

### Stage 2 (Detail Pages)
- **Speed:** 1-5 seconds per prospect
- **Throughput:** 12-60 prospects/minute (with 2s delay)
- **Total:** 720-3600 prospects/hour

### Example: 1000 Prospects

| Approach | Time | Data Quality |
|----------|------|--------------|
| Stage 1 only | 5-10 minutes | Basic (no contact info) |
| Stage 1 + Stage 2 (all) | 35-85 minutes | Complete (if available) |
| Stage 1 + Stage 2 (selective) | 10-20 minutes | Mixed (enriched subset) |

---

## Next Steps

1. **Enable automatic enrichment:**
   ```bash
   # Add to .env
   ENRICHMENT_ENABLED=1
   
   # Restart Celery Beat
   celery -A leads_app beat -l info
   ```

2. **Test manual enrichment:**
   ```bash
   python manage.py enrich_prospects --dry-run
   python manage.py enrich_prospects --max-prospects 5
   ```

3. **Monitor results:**
   - Check Django Admin for enriched prospects
   - Review Google Sheets for new data
   - Check Celery logs for errors

4. **Tune settings:**
   - Adjust `ENRICHMENT_BATCH_SIZE` based on results
   - Increase/decrease `ENRICHMENT_DELAY` if getting blocked
   - Enable Playwright if using LinkedIn/Twitter

---

## Summary

✅ **Two-stage scraping is now implemented and ready to use!**

- **Stage 1:** Fast discovery of prospects from listing pages (automatic)
- **Stage 2:** Selective enrichment from detail pages (manual or automatic)
- **Automation:** Configure via `.env` for hands-off operation
- **Flexibility:** Manual commands for selective/targeted enrichment
- **Monitoring:** Celery logs + Django Admin + Google Sheets

**Remember:** Most platforms don't show contact info publicly. Use this tool for discovery and qualification, then do manual research or use paid enrichment services for complete contact details.

For questions or issues, see `TROUBLESHOOTING.md` or check the Celery worker logs.