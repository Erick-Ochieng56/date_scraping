# Quick Start - Two-Stage Scraping System

## 5-Minute Setup

### 1. Enable Automatic Enrichment

Add to your `.env` file:
```env
ENRICHMENT_ENABLED=1
ENRICHMENT_BATCH_SIZE=25
ENRICHMENT_INTERVAL_SECONDS=1800
ENRICHMENT_DELAY=2.0
```

### 2. Restart Celery Beat

```bash
# Stop current beat process (Ctrl+C)
# Then restart:
celery -A leads_app beat -l info
```

### 3. Verify It's Working

Check the logs:
```
[INFO] Celery beat: auto-enrich-prospects scheduled every 30 minutes
```

Done! The system will now:
- ✅ Scrape listing pages every 2 hours (Stage 1)
- ✅ Enrich 25 prospects every 30 minutes (Stage 2)
- ✅ Sync to Google Sheets automatically

---

## Manual Enrichment

Enrich prospects immediately:
```bash
# Test first (dry run)
python manage.py enrich_prospects --dry-run

# Enrich 50 prospects
python manage.py enrich_prospects --max-prospects 50 --platform eventbrite

# Enrich specific prospects
python manage.py enrich_prospects --prospect-ids 123 124 125
```

---

## Testing

Test selectors before deploying:
```bash
python test_config.py
```

Expected output:
```
✓ Extracted 64 items
✓ RESULT: Selectors are working!
Statistics:
  Filled fields: 192/192 (100%)
```

---

## Monitoring

### Check Recent Prospects
```bash
python manage.py shell --command "from leads.models import Prospect; [print(f'{p.id}: {p.event_name} | {p.company}') for p in Prospect.objects.order_by('-created_at')[:5]]"
```

### Check Enrichment Logs
```bash
tail -f celery_worker.log | grep -i "enrich"
```

### Check Admin
- Prospects: http://localhost:8000/admin/leads/prospect/
- Scrape Runs: http://localhost:8000/admin/scraper/scraperun/

---

## What Gets Enriched?

### Eventbrite
- ✅ Organizer name
- ⚠️ Website (sometimes)
- ✅ Full description
- ✅ Detailed location
- ❌ Email (not available)

### Meetup
- ✅ Group name
- ⚠️ Website (if provided)
- ✅ Full description
- ✅ Host name
- ❌ Email (not available)

### LinkedIn/Twitter
- ⚠️ Requires Playwright: `ENRICHMENT_USE_PLAYWRIGHT=1`
- ⚠️ May require authentication
- ⚠️ High risk of blocking

---

## Troubleshooting

### No data extracted?
```bash
# Check if selectors are working
python test_config.py

# Check recent scrape runs
# Admin → Scraper → Scrape Runs → View errors
```

### Getting blocked?
```bash
# Increase delay
python manage.py enrich_prospects --delay 5.0

# Reduce batch size
python manage.py enrich_prospects --max-prospects 10
```

### Need more detailed docs?
- `TWO_STAGE_SCRAPING.md` - Complete guide
- `SCRAPING_FAQ.md` - Common questions
- `BLANK_DATA_FIX.md` - Selector issues
- `DATA_AVAILABILITY_GUIDE.md` - What data is available

---

## Summary

✅ **Automatic two-stage scraping is now active!**

- Stage 1: Fast discovery (every 2 hours)
- Stage 2: Selective enrichment (every 30 minutes)
- Testing: `python test_config.py`
- Manual: `python manage.py enrich_prospects`

**Remember:** Email/phone are rarely available. Use this for discovery + qualification, then do manual research for contact info.