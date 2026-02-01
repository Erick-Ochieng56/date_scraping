# How to Run the Automated Scraping System

## Quick Start Guide

### Step 1: Prerequisites

1. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Set up Environment Variables:**
   Create/update your `.env` file with:
   ```env
   # Required
   DJANGO_SECRET_KEY=your-secret-key-here
   DJANGO_DEBUG=1
   
   # Google Sheets (Required for lead output)
   GSHEETS_ENABLED=1
   GSHEETS_CREDENTIALS_JSON={"type":"service_account",...}
   GSHEETS_SPREADSHEET_ID=your-spreadsheet-id
   GSHEETS_LEADS_RANGE=Leads!A:Z
   
   # Database (SQLite for local dev, or PostgreSQL)
   # DATABASE_URL=postgresql://user:pass@localhost/dbname
   
   # Redis (Required for Celery)
   REDIS_URL=redis://localhost:6379/0
   # Or: CELERY_BROKER_URL=redis://localhost:6379/0
   ```

3. **Start Redis:**
   ```powershell
   # If Redis is installed locally
   redis-server
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:7
   ```

4. **Run Database Migrations:**
   ```powershell
   python manage.py migrate
   ```

### Step 2: Set Up Scrape Targets

You have three options:

#### Option A: Auto-Create via Admin (Easiest)
1. Start Django server: `python manage.py runserver`
2. Go to: `http://localhost:8000/admin/scraper/scrapetarget/`
3. Visit: `http://localhost:8000/admin/scraper/scrapetarget/auto-create/?url=YOUR_EVENT_URL`
4. Review and adjust the auto-generated config

#### Option B: Sync from Config File
1. Edit `targets.json` with your targets
2. Run: `python manage.py sync_targets --file targets.json --update`

#### Option C: Manual Entry in Admin
1. Go to Django admin
2. Add ScrapeTarget manually with proper config

### Step 3: Run the Automated System

You need **3 terminal windows** running simultaneously:

#### Terminal 1: Django Web Server
```powershell
python manage.py runserver
```
- Provides admin interface at `http://localhost:8000/admin/`
- Health check at `http://localhost:8000/healthz`

#### Terminal 2: Celery Worker
```powershell
celery -A leads_app worker -l info
```
- Processes scraping tasks
- Handles Google Sheets sync
- Shows real-time task execution

#### Terminal 3: Celery Beat (Scheduler)
```powershell
celery -A leads_app beat -l info
```
- Schedules automatic scraping
- Runs enabled targets on their schedule (`run_every_minutes`)
- Default: checks every 5 minutes for targets to scrape

### Step 4: Verify It's Working

1. **Check Celery Beat Schedule:**
   - Look for: `scrape-enabled-targets` task in beat logs
   - Runs every 5 minutes (configurable via `SCRAPE_ALL_INTERVAL_SECONDS`)

2. **Check Worker Logs:**
   - Should see: `Task scraper.tasks.scrape_target[...] received`
   - Should see: `Task sheets_integration.tasks.append_lead_to_sheet[...] received`

3. **Check Google Sheets:**
   - New leads should appear automatically
   - Check the "Leads" sheet in your configured spreadsheet

4. **Check Django Admin:**
   - Go to: `http://localhost:8000/admin/scraper/scraperun/`
   - See scrape run history and results

## Automation Schedule

### How It Works:

1. **Celery Beat** runs every 5 minutes (default)
2. **Beat** triggers `enqueue_enabled_targets` task
3. **Task** finds all enabled `ScrapeTarget` objects
4. **For each target**, it checks:
   - Is it enabled? ✓
   - Has `run_every_minutes` passed since last run?
5. **If ready**, queues a `scrape_target` task
6. **Worker** executes the scrape:
   - Fetches HTML/renders page
   - Extracts items using selectors
   - Creates/updates Lead records
   - Pushes to Google Sheets automatically

### Customize Schedule:

**Per-Target Schedule:**
- Edit `ScrapeTarget.run_every_minutes` in admin
- Example: `120` = runs every 2 hours

**Global Check Interval:**
- Set `SCRAPE_ALL_INTERVAL_SECONDS=300` in `.env`
- Default: 300 seconds (5 minutes)
- This is how often the system checks for targets to run

## Manual Triggers

### Trigger Scrape via Admin:
1. Go to: `http://localhost:8000/admin/scraper/scrapetarget/`
2. Select targets
3. Choose "Trigger scrape for selected targets" from Actions dropdown
4. Click "Go"

### Trigger Scrape via API:
```powershell
curl -X POST http://localhost:8000/ops/trigger-scrape `
  -H "X-OPS-TOKEN: your-ops-token" `
  -H "Content-Type: application/json" `
  -d '{"target_id": 1}'
```

### Trigger Single Target Test:
- Click "Test Scrape" button next to any target in admin list

## Monitoring

### Check Scrape Runs:
- Admin: `http://localhost:8000/admin/scraper/scraperun/`
- Shows: Status, item count, created/updated leads, errors

### Check Leads:
- Admin: `http://localhost:8000/admin/leads/lead/`
- Shows all scraped leads

### Check Google Sheets:
- Open your configured spreadsheet
- New rows appear automatically as leads are scraped

### Check Logs:
- **Worker logs**: Real-time task execution
- **Beat logs**: Schedule execution
- **Django logs**: Web requests and errors

## Troubleshooting

### "No targets being scraped"
- Check targets are **enabled** in admin
- Check `run_every_minutes` is set
- Check Celery Beat is running
- Check worker is running

### "Leads not appearing in Google Sheets"
- Verify `GSHEETS_ENABLED=1`
- Verify `GSHEETS_SPREADSHEET_ID` is correct
- Check service account has access to sheet
- Check worker logs for errors

### "Celery worker errors"
- On Windows: Should use `solo` pool (automatic)
- Check Redis is running: `redis-cli ping` should return `PONG`
- Check Redis URL in `.env`

### "Target scraping fails"
- Check target config has `item_selector` and `fields`
- Test manually via "Test Scrape" button
- Check ScrapeRun admin for error messages

## Production Deployment

For production, use:
- **Docker Compose** (recommended) - see `docker-compose.yml`
- **Supervisor/systemd** for process management
- **PostgreSQL** instead of SQLite
- **Redis** for Celery broker
- Set `DJANGO_DEBUG=0` and proper `DJANGO_SECRET_KEY`

## Quick Command Reference

```powershell
# Start everything (3 terminals)
python manage.py runserver
celery -A leads_app worker -l info
celery -A leads_app beat -l info

# Sync targets from config
python manage.py sync_targets --file targets.json --update

# Create superuser (first time)
python manage.py createsuperuser

# Check system health
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

