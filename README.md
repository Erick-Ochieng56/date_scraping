# date_scraping

Production-ready Django service that:
- Scrapes event/meeting data on a schedule (Celery + Redis)
- Creates Prospects (pre-contact discovery) automatically
- Syncs Prospects to Google Sheets for team review
- Converts Prospects to Leads (post-contact) for full CRM workflow
- Optional: Syncs Leads to Perfex CRM (when API key available)

**📖 For detailed setup and running instructions, see [HOW_TO_RUN.md](HOW_TO_RUN.md)**

## Quick Start

### Run the Automated System (3 terminals needed):

**Terminal 1 - Django Server:**
```powershell
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```powershell
celery -A leads_app worker -l info
```

**Terminal 3 - Celery Beat (Scheduler):**
```powershell
celery -A leads_app beat -l info
```

The system will automatically:
- Check for enabled targets every 5 minutes
- Scrape targets based on their `run_every_minutes` schedule
- Create Prospects and push them to Google Sheets immediately

## Local development (venv)
Create and activate a virtualenv, then:

```powershell
pip install -r requirements.txt
copy .env.example .env
```

Run migrations + server:

```powershell
$env:DJANGO_DEBUG='1'
$env:DJANGO_SECRET_KEY='dev-secret'
python manage.py migrate
python manage.py runserver
```

Run workers:

```powershell
celery -A leads_app worker -l info
celery -A leads_app beat -l info
```

**Note for Windows users:** The Celery worker is automatically configured to use the `solo` pool on Windows to avoid multiprocessing issues. For better performance on Windows, you can use the threads pool by setting `CELERY_WORKER_POOL=threads` in your `.env` file.

## Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

- Web: `http://localhost:8000/admin/`
- Health: `http://localhost:8000/healthz`
- Ready: `http://localhost:8000/readyz`

## Configure scrape targets

You have **three methods** to manage scrape targets:

### Method 1: Manual (Django Admin)
Create `ScrapeTarget` rows in Django admin with a `config` like:

```json
{
  "item_selector": ".item",
  "fields": {
    "full_name": ".name",
    "email": ".email",
    "phone": ".phone",
    "date": ".date"
  },
  "next_page_selector": "a.next",
  "max_pages": 3,
  "timeout_seconds": 30
}
```

### Method 2: Config File Sync (Bulk Management)
Use `targets.json` to define multiple targets and sync them:

```bash
# Edit targets.json with your targets
python manage.py sync_targets --file targets.json --update
```

**Example `targets.json`:**
```json
[
  {
    "name": "Eventbrite - Tech Events",
    "start_url": "https://www.eventbrite.com/d/united-states/tech/events/",
    "enabled": true,
    "target_type": "html",
    "run_every_minutes": 120,
    "config": {
      "item_selector": ".event-card",
      "fields": {
        "full_name": ".event-title",
        "event_date": ".event-date",
        "source_url": "a.event-link@href"
      },
      "next_page_selector": "a.pagination-next",
      "max_pages": 5
    }
  }
]
```

**Command options:**
- `--file PATH` - Path to config file (default: `targets.json`)
- `--update` - Update existing targets instead of skipping
- `--disable-missing` - Disable targets not in config file
- `--dry-run` - Preview changes without applying

### Method 3: Auto-Discovery API (Intelligent Creation)
Automatically detect platform and generate config:

```bash
curl -X POST http://localhost:8000/ops/auto-create-target \
  -H "X-OPS-TOKEN: your-token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.eventbrite.com/d/united-states/events/", "name": "Eventbrite Auto"}'
```

**Supported platforms** (auto-detected):
- Eventbrite (85-95% accuracy)
- Meetup (85-95% accuracy)
- Facebook Events
- Eventful
- Brown Paper Tickets
- Ticketmaster
- Generic sites (40-60% accuracy, needs manual tuning)

**Response:**
```json
{
  "created": true,
  "target_id": 5,
  "name": "Auto-Eventbrite",
  "platform": "eventbrite",
  "target_type": "html",
  "message": "Target created successfully. Platform: eventbrite"
}
```

### Periodic Auto-Sync
Enable automatic syncing from `targets.json`:

```bash
# In .env file
TARGETS_SYNC_ENABLED=1
TARGETS_SYNC_FILE=targets.json
TARGETS_SYNC_SCHEDULE_HOUR=0  # Daily at midnight
TARGETS_SYNC_SCHEDULE_MINUTE=0
```

The system will automatically sync targets daily (configurable via Celery Beat).

## Workflow: Google Sheets → Manual CRM Entry

**Current Process (No CRM API Key Yet):**
1. **Scraping**: System scrapes event websites (Eventbrite, Meetup, etc.)
2. **Auto-Sync to Google Sheets**: New leads are automatically pushed to Google Sheets for review
3. **Manual Review**: Review leads in Google Sheets or Django Admin
4. **Status Workflow**: Mark leads as Contacted → Interested → Rejected (or directly to Interested)
5. **Manual CRM Entry**: Manually add interested leads to Perfex CRM

**Future (When API Key Available):**
- Set `PERFEX_SYNC_ENABLED=1` in `.env` to enable automatic CRM injection
- Leads will sync directly to Perfex CRM after scraping

## Perfex CRM Integration (Optional - Disabled by Default)
**Currently disabled** - enable only when API key is available.

Set in `.env` when ready:
- `PERFEX_SYNC_ENABLED=1` - Enable automatic CRM sync
- `PERFEX_BASE_URL` (e.g. `https://your-perfex.example.com`)
- `PERFEX_API_TOKEN` (REST API module token)
- Optional: `PERFEX_DEFAULTS_JSON` to provide required ids (status/source/etc)

## Ops endpoints
Requires `OPS_TOKEN` and header `X-OPS-TOKEN: <token>`.

- `POST /ops/trigger-scrape` body `{"target_id": 1}` (optional) to enqueue scrape
- `POST /ops/trigger-sync` body `{"lead_id": 123}` (optional) to enqueue sync
- `POST /ops/auto-create-target` body `{"url": "...", "name": "..."}` to auto-create target

## Workflow: Prospects → Leads

The system uses a two-stage workflow:

### Stage 1: Prospects (Pre-Contact Discovery)
- **Scraped automatically** from event websites
- **Minimal fields**: Event Name, Company, Email, Phone, Website
- **Auto-synced to "Prospects" sheet** in Google Sheets
- **Status**: NEW → CONTACTED → CONVERTED/REJECTED

### Stage 2: Leads (Post-Contact Qualification)
- **Created manually** when Prospects are contacted
- **Full CRM fields**: All contact info, address, position, etc.
- **Status**: CONTACTED → INTERESTED → SYNCED/REJECTED
- **Can be synced to Perfex CRM** when API key is available

### Conversion Process:
1. Review Prospects in Google Sheets or Django Admin
2. Contact the organization
3. In Django Admin: Select Prospects → "Convert to Leads" action
4. Leads appear in separate admin section with full CRM workflow

## Google Sheets Integration

**Prospects Sheet (Primary Output):**
- Automatically created and populated
- **Columns**: Event Name, Company, Email, Phone, Website (5 columns)
- **Sheet name**: "Prospects" (default)
- **Range**: `Prospects!A:E`

**Leads Sheet (Optional):**
- For qualified Leads ready for CRM
- **Columns**: Full CRM fields (24 columns)
- **Sheet name**: "Leads" (default)
- **Range**: `Leads!A:Z`

**Environment Variables:**
```env
GSHEETS_ENABLED=1
GSHEETS_CREDENTIALS_JSON={"type":"service_account",...}
GSHEETS_SPREADSHEET_ID=your-spreadsheet-id
GSHEETS_PROSPECTS_RANGE=Prospects!A:E  # Optional, defaults to Prospects!A:E
GSHEETS_LEADS_RANGE=Leads!A:Z  # Optional, defaults to Leads!A:Z
```

**Setup:**
1. Create Google Cloud service account and download JSON key
2. Share your Google Sheet with the service account email
3. Set environment variables
4. Prospects will automatically sync to Sheets when scraped

