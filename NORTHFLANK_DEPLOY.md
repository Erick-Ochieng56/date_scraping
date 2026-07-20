# Deploying to Northflank (free tier)

This guide deploys the whole system on Northflank's free **Developer Sandbox**, which allows exactly **2 services, 2 jobs, and 1 addon**. That budget forces the layout:

| Slot | What runs there |
|---|---|
| **Addon (the one free database)** | PostgreSQL — the only thing that must be durable |
| **Service 1 — `redis`** | Plain `redis:7-alpine` image. Celery broker + result backend. Ephemeral is fine here: if it restarts, queued tasks are lost but Celery Beat re-enqueues everything on its next tick. |
| **Service 2 — `app`** | One container built from the repo-root [Dockerfile](Dockerfile), running **gunicorn + Celery worker + embedded Beat together** (`START_MODE=all`). Django also serves the built React SPA (`DJANGO_SERVE_SPA=1`), so no separate frontend service is needed. |

The same image supports `START_MODE=web|worker|worker-beat|beat`, so when you later move to pay-as-you-go you split it into separate services by changing one env var per service — no rebuild (see [Migrating off the free tier](#migrating-off-the-free-tier)).

**Files involved** (all committed in this repo):
- [Dockerfile](Dockerfile) — multi-stage: builds the SPA with Node, then the Python image (SPA copied to `/frontend/dist`, `collectstatic` baked in).
- [deploy/start.sh](deploy/start.sh) — entrypoint with the `START_MODE` switch; runs migrations and optional superuser bootstrap on boot.
- [.dockerignore](.dockerignore) — keeps `backend/.env` (secrets), `venv/`, `node_modules/` out of the image.
- [deploy/northflank-template.json](deploy/northflank-template.json) — optional IaC template for the whole stack. Validate it in Northflank's template editor before running; the manual steps below are the reference path.

---

## 0. Before you start

1. **Rotate any secrets that ever lived in `backend/.env`.** The audit found live keys there historically (Google service account, Serper, Gemini, Django secret). Generate fresh values for production — never paste the old ones into Northflank.
2. Generate a new Django secret key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
3. Push the repo (with the `Dockerfile`, `deploy/`, `.dockerignore`) to GitHub — Northflank builds from the repo.
4. Create a Northflank account (free tier requires a card) and link your GitHub account: **Account settings → Git integrations**.

## 1. Create the project

Northflank UI → **Create project** → name `date-scraping`, pick the region closest to you. Everything below lives inside this project.

## 2. PostgreSQL addon

1. Project → **Addons → Create addon → PostgreSQL**.
2. Name `db`, latest version, smallest plan, 1 replica, ~4GB storage.
3. After it provisions, open **Connection details** and copy the **Postgres connection URI** (`postgresql://user:pass@host:5432/dbname`). This becomes `DATABASE_URL` in step 4. Use the **internal** host, not the external one — the app talks to it inside the project network.

## 3. Redis service

1. Project → **Services → Create service → Deployment service**.
2. Deployment source: **External image** → `redis:7-alpine`.
3. Name `redis`, smallest compute plan, 1 instance.
4. **Networking / Ports**: add a **TCP** port `6379`, **not** publicly exposed.
5. After deploy, note the internal hostname shown on the port (typically just the service name, `redis`, works inside the project). `REDIS_URL` becomes `redis://redis:6379/0` — if the UI shows a longer private DNS name for the port, use that instead.

## 4. The app service

1. Project → **Services → Create service → Combined service** (build + deploy).
2. Source: your GitHub repo, branch `main`.
3. Build type **Dockerfile**: path `/Dockerfile`, context `/` (repo root — the build needs both `frontend/` and `backend/`).
4. Compute: the largest plan the free tier lets you pick (the container runs gunicorn + Celery + Beat together, so give it everything available). 1 instance.
5. **Networking**: HTTP port `8000`, publicly exposed. Health checks: liveness `GET /healthz`, readiness `GET /readyz` (readiness checks the DB and returns 503 until it's reachable).
6. **Environment variables** (Service → Environment, or a project-level Secret Group):

   **Required:**

   | Variable | Value |
   |---|---|
   | `START_MODE` | `all` |
   | `DJANGO_SECRET_KEY` | the fresh key from step 0 (mark as secret) |
   | `DJANGO_DEBUG` | `0` |
   | `DATABASE_URL` | the Postgres URI from step 2 (mark as secret) |
   | `REDIS_URL` | `redis://redis:6379/0` (from step 3) |
   | `DJANGO_SERVE_SPA` | `1` |
   | `DJANGO_ALLOWED_HOSTS` | `.code.run` (Northflank's generated domains; add your custom domain later) |
   | `DJANGO_BEHIND_HTTPS_PROXY` | `1` (Northflank terminates TLS and forwards HTTP) |
   | `DJANGO_USE_X_FORWARDED_HOST` | `1` |
   | `DJANGO_PUBLIC_ORIGIN` | set **after first deploy** — see step 5 |

   **Sizing (free-tier-safe defaults):**

   | Variable | Value |
   |---|---|
   | `CELERY_WORKER_POOL` | `threads` |
   | `CELERY_CONCURRENCY` | `2` |
   | `GUNICORN_WORKERS` | `1` |
   | `GUNICORN_THREADS` | `4` |
   | `CRAWLER_MAX_DOMAINS_PER_RUN` | `50` (default is 500 — far too much for one small worker) |

   **Feature keys (optional — leave unset to disable the feature):**

   | Variable | Purpose |
   |---|---|
   | `GEMINI_API_KEY` | AI search + crawler AI qualification |
   | `SERPER_API_KEY` | Serper.dev discovery |
   | `OPS_TOKEN` | protects the `/ops/*` endpoints |
   | `GSHEETS_ENABLED` + `GSHEETS_CREDENTIALS_JSON` + `GSHEETS_SPREADSHEET_ID` | Google Sheets sync (set `GSHEETS_ENABLED=0` if unused) |
   | `PERFEX_SYNC_ENABLED` | keep `0` until Perfex is ready |

   **First boot only (remove after logging in):**

   | Variable | Purpose |
   |---|---|
   | `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` / `DJANGO_SUPERUSER_EMAIL` | `start.sh` creates the admin account automatically on boot |

7. Create the service. The first build takes a while (npm build + pip install, spaCy model included via requirements).

## 5. First-deploy loop ends: set the public origin

1. When the app deploys, copy its generated URL from the service header (something like `https://p01--app--date-scraping--yourname.code.run`).
2. Set `DJANGO_PUBLIC_ORIGIN` to that exact URL (scheme included, no trailing slash) and redeploy. Without it, session login POSTs fail CSRF checks.
3. Visit `https://<your-url>/readyz` — expect `{"status": "ok", ...}` with `"db": "ok"`.
4. Log into the SPA at `/login` with the bootstrap superuser, then **delete the `DJANGO_SUPERUSER_*` env vars**.
5. Create staff users from the SPA's admin Users page (or run `python manage.py create_staff_user` in the service's shell tab).

## Free-tier limitations to expect

- **No Playwright/Chromium.** The image builds without it by default (`INSTALL_PLAYWRIGHT=0` build arg): Chromium doesn't fit small containers. Playwright-type scrape targets fail with a clean "Playwright is not available" error; HTML targets and the crawler work normally (the crawler's JS-heavy fallback just logs and continues).
- **One shared container** means a heavy crawl can slow API responses. The sizing envs above keep Celery to 2 threads; resist raising them until you have more RAM.
- **Redis is ephemeral.** A Redis restart drops queued (not-yet-started) tasks; Beat re-enqueues scheduled work on its next tick. Don't rely on the queue as storage.
- **Not for production** per Northflank's own terms — fine for the current review/testing phase.
- **`.code.run` in `DJANGO_ALLOWED_HOSTS` is broad** (any Northflank-generated domain routes only to your service anyway). When you add a custom domain, list it explicitly and optionally replace `.code.run` with your exact generated host.

## Migrating off the free tier

When you move to pay-as-you-go, everything is env-driven — same image:

1. **Split the combined container**: create a second service from the same build with `START_MODE=worker-beat` (or `worker` + a separate `beat`), and set the existing app service to `START_MODE=web`. Web latency stops competing with crawls.
2. **Swap the Redis service for a managed Redis addon** (paid tiers allow more addons) and update `REDIS_URL`.
3. **Enable Playwright**: set the build arg `INSTALL_PLAYWRIGHT=1` on the worker service's build settings and give that service a bigger plan (Chromium wants 1GB+). The scraper's process-tree kill and concurrency guard already protect against runaway browsers.
4. Raise `CELERY_CONCURRENCY`, `GUNICORN_WORKERS`, and `CRAWLER_MAX_DOMAINS_PER_RUN` to match the new plans.
5. Consider 2 instances of the web service once traffic justifies it (migrations in `start.sh` are safe to race, but you can also move `migrate` to a Northflank job).
