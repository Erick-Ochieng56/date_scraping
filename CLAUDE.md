# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A lead-generation system: Django 5.2 backend (`backend/`) + React 19/Vite SPA (`frontend/`). Two independent pipelines populate the same `Prospect` → `Lead` models:

- **`scraper`**: schedule-driven scraping of configured target URLs (Eventbrite, Meetup, etc. via CSS-selector configs), Playwright-in-subprocess rendering, two-stage (listing scrape → detail-page enrichment).
- **`crawler`** (primary pipeline): Bing/Serper domain discovery → BFS crawl → spaCy/rule-based/Gemini scoring → East-Africa "active buyer" qualification → promotes into `Prospect`.

Both feed `leads.Prospect` (pre-contact) → `Prospect.convert_to_lead()` → `leads.Lead` (post-contact CRM record). Leads can optionally sync to Perfex CRM (`crm_integration`, gated by `PERFEX_SYNC_ENABLED`) and Prospects/Leads auto-sync to Google Sheets (`sheets_integration`, gated by `GSHEETS_ENABLED`).

The React SPA (`frontend/`) is the sole live UI — staff operator view at `/`, admin portal at `/admin`. The legacy server-rendered Bootstrap dashboard has been removed from `backend/dashboard/` (views.py/api_views.py/forms.py deleted, `django_bootstrap5` uninstalled); everything under `/dashboard/` is now JSON API only (session-auth DRF + SSE streaming), consumed exclusively by the SPA.

## Backend apps (`backend/`)

| App | Role |
|---|---|
| `core` | health checks (`/healthz`, `/readyz`), `/ops/*` trigger endpoints, SPA catch-all route (`core.views.react_spa_catch_all`) |
| `leads` | models only — `Prospect`/`Lead`, conversion logic |
| `scraper` | Stage-1/Stage-2 scraping, Celery tasks, auto-discovery of platform configs |
| `crawler` | independent discovery→crawl→score pipeline, own `CrawlRun`/`CrawlSource`/`DiscoveredDomain` models |
| `crm_integration` | Perfex CRM sync via REST client + Celery retry/backoff |
| `sheets_integration` | Google Sheets export via service account |
| `dashboard` | JSON API only: DRF views under `dashboard/api/` (`api/v1/...`, `api/admin/v1/...`), session-based auth (`auth_api.py`), SSE run streaming, CSV export (`export_views.py`), target-creation wizard (`wizard_views.py`) |

`REST_FRAMEWORK` still lists `JWTAuthentication`/`SIMPLE_JWT` in settings, but every real view uses `SessionAuthentication` — there is no `/api/token/` endpoint; treat the JWT config as inert.

## Commands

### Backend (from `backend/`, venv activated)

```powershell
python manage.py runserver
python manage.py migrate
python manage.py test                          # Django test runner (no pytest)
python manage.py test dashboard                # single app
python manage.py test dashboard.tests.DashboardV1ApiTests   # single test case
python manage.py createsuperuser                # admin role
python manage.py create_staff_user              # staff/portal role, no Django admin access
python manage.py sync_targets --file targets.json --update --dry-run
celery -A leads_app worker -l info
celery -A leads_app beat -l info
```

Windows Celery worker auto-uses the `solo` pool; set `CELERY_WORKER_POOL=threads` in `.env` for better throughput.

### Frontend (from `frontend/`)

```bash
npm run dev          # Vite dev server on :5173, proxies /dashboard to Django :8000
npm run build         # tsc -b && vite build
npm run test          # vitest run
npm run test:watch
npm run lint           # eslint .
```

### Docker Compose (`backend/docker-compose.yml`)

Brings up Postgres, Redis, `web` (gunicorn), `worker`, and `beat` services. Run from `backend/`: `docker compose up --build`.

### Production / Northflank

Deployed on Northflank's **free tier** (2 services, 1 addon): Postgres addon + `redis:7-alpine` service + one combined container (gunicorn + Celery worker with embedded beat, `START_MODE=all`) built from the **repo-root `Dockerfile`** (multi-stage: builds the SPA, Django serves it via `DJANGO_SERVE_SPA=1`). Entrypoint `deploy/start.sh` supports `START_MODE=all|web|worker|worker-beat|beat` so the same image splits into separate services on a paid plan. Playwright/Chromium is excluded by default (`INSTALL_PLAYWRIGHT=0` build arg) — too heavy for free-tier containers. Full guide: `NORTHFLANK_DEPLOY.md`; IaC template: `deploy/northflank-template.json`.

## Frontend structure (`frontend/src`)

```
app/           # router, lazy pages, nav
features/      # domain pages: pipeline, scraper, crawler, admin, home, ai-search
shared/        # api client, components, hooks, layouts
pages/         # thin re-exports during migration
```

API calls go through `shared/api/pipeline` (versioned `/dashboard/api/v1/...` endpoints). `@/lib/api/dashboard` is `@deprecated` — don't add new callers there; a couple of detail pages (`ProspectDetailPage.tsx`, `LeadDetailPage.tsx`) still import it as known tech debt.

Realtime: run lists poll while jobs are active; the staff home page also subscribes to `/dashboard/api/v1/stream/runs/` (SSE) and falls back to polling if the stream drops.

## Auth model

Session-based (not JWT). Two roles distinguished by group membership / `is_staff`, not a formal permission system:
- **Admin**: `is_staff` (via `createsuperuser` or SPA Users page) → lands on `/admin`.
- **Staff**: `scraper` group (via `create_staff_user`) → portal access, no Django admin.

## Known repo-wide caveats (from prior full-codebase audits)

- `backend/.env` is gitignored. Keep local credentials there (or in the host secret store) and do not commit that file or paste live values into docs.
- Activity Log / Notifications models and helpers (`log_activity()`, `create_notification()`) exist in `dashboard` but are called from nowhere — non-functional despite being described as complete in older docs.
- `django_filters`/`django_tables2` are installed apps with no actual usage in the codebase.
- Only Eventbrite scraping is validated end-to-end; other platform selector configs are aspirational/untested per `backend/TWO_STAGE_SCRAPING.md`.
- The 20+ markdown docs under `backend/` (`DASHBOARD_PHASE*_COMPLETE.md`, `IMPLEMENTATION_SUMMARY.md`, etc.) describe the now-removed Bootstrap dashboard and predate the SPA becoming canonical — treat them as historical, not current, and prefer `backend/HOW_TO_RUN.md` and `frontend/README.md` for up-to-date operational instructions.
- See `CODEBASE_REANALYSIS.md` at repo root for the full audit this file is derived from.
