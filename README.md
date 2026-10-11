# date_scraping

Lead generation for translation and event prospects. A Django API and a React app share one set of records: discovered organizations land as **Prospects**, and contacting one turns it into a **Lead**.

Two pipelines fill that list:

- **Crawler** (primary): search-based domain discovery, a site crawl, then scoring and qualification. Optional Gemini and Serper keys improve extraction and search.
- **Scraper**: scheduled scrapes of configured listing URLs (Eventbrite and others), with an optional detail-page pass.

The React app in `frontend/` is the live UI. Staff use `/`. Admins use `/admin`. Django serves JSON under `/dashboard/api/` and, in production, can serve the built SPA itself.

## Layout

| Path | Role |
|---|---|
| `backend/` | Django 5.2 project (`leads_app`), Celery worker, and the data pipelines |
| `frontend/` | React 19 / Vite staff and admin app |
| `Dockerfile` | Production image: built SPA plus gunicorn and Celery |
| `deploy/` | Container entrypoint and the Northflank template |
| `backend/.env.example` | Local configuration template. Copy it to `backend/.env` |

`backend/.env` is gitignored. Put API keys and service-account credentials only there, or in the host's secret store.

## Local development

Prerequisites: Python 3.12, Node.js 22, and Redis. Postgres is optional locally; without `DATABASE_URL`, Django uses SQLite.

**API** (from `backend/`, with a virtualenv active):

```powershell
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

**UI** (from `frontend/`):

```powershell
npm install
npm run dev
```

Vite runs on port 5173 and proxies `/dashboard` to Django on port 8000. Open `http://localhost:5173/login`.

**Background jobs** (from `backend/`). Scrapes, crawls, and optional CRM or Sheets sync run through Celery:

```powershell
celery -A leads_app worker -l info
celery -A leads_app beat -l info
```

On Windows the worker uses the `solo` pool. Set `CELERY_WORKER_POOL=threads` in `.env` for more throughput.

### Accounts

Session login, not JWT.

- **Admin:** `python manage.py createsuperuser`, then the app opens `/admin`.
- **Staff:** `python manage.py create_staff_user`. These users can use the portal and cannot use Django admin.

### Tests

```powershell
# from backend/
python manage.py test

# from frontend/
npm run test
npm run lint
```

## Docker Compose

From `backend/`, with `backend/.env` present:

```powershell
docker compose up --build
```

That starts Postgres, Redis, the web process, a worker, and beat. The app is on `http://localhost:8000`. Health checks are `/healthz` and `/readyz`.

## Production

The repo-root `Dockerfile` builds the SPA and runs Django with Celery. `deploy/start.sh` selects the process with `START_MODE=all|web|worker|worker-beat|beat`. The free-tier Northflank layout uses one combined container (`START_MODE=all`) plus Redis and a Postgres addon. See [NORTHFLANK_DEPLOY.md](NORTHFLANK_DEPLOY.md).

Playwright is off in that image by default (`INSTALL_PLAYWRIGHT=0`). HTML scrapes and the crawler still run. Browser-rendered targets need a heavier image.

## Further docs

- [frontend/README.md](frontend/README.md) covers the SPA, proxy, and ngrok setup.
- [backend/.env.example](backend/.env.example) lists every setting.
- Older notes under `backend/` describe a Django template dashboard that has been removed. Prefer this file and `frontend/README.md` for how to run the app.
