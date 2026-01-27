# date_scraping

Production-ready Django service that:
- Scrapes lead/date data on a schedule (Celery + Redis)
- Stores normalized leads in Postgres (Django models)
- Syncs leads into Perfex CRM via REST API

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

## Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

- Web: `http://localhost:8000/admin/`
- Health: `http://localhost:8000/healthz`
- Ready: `http://localhost:8000/readyz`

## Configure scrape targets
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

## Perfex integration
Set in `.env`:
- `PERFEX_BASE_URL` (e.g. `https://your-perfex.example.com`)
- `PERFEX_API_TOKEN` (REST API module token)
- Optional: `PERFEX_DEFAULTS_JSON` to provide required ids (status/source/etc)

## Ops endpoints
Requires `OPS_TOKEN` and header `X-OPS-TOKEN: <token>`.

- `POST /ops/trigger-scrape` body `{"target_id": 1}` (optional) to enqueue scrape
- `POST /ops/trigger-sync` body `{"lead_id": 123}` (optional) to enqueue sync

