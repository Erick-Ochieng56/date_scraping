# date_scraping — Full Codebase Reanalysis
*Generated 2026-07-18*

## 1. What this project actually is

A lead-generation system with a Django 5.2 backend and **two separate frontends** that no doc in the repo acknowledges exist together:

- A server-rendered Bootstrap 5 + Chart.js admin dashboard (Django templates, `backend/dashboard/`), built out in five documented "phases."
- A modern React 19 + Vite + TypeScript + Tailwind 4 + shadcn SPA (`frontend/`), which calls the same backend over a versioned JSON API (`/dashboard/api/v1/...`).

`.env`/`.env.example` show `DJANGO_SERVE_SPA=1` is actually enabled, meaning the React app is the live UI and the Bootstrap templates are likely legacy — but nothing in the repo's 22 markdown docs says so. This is the single biggest documentation gap: the project's own paper trail describes building a dashboard that appears to have been superseded.

The backend has **7 Django apps**, not the 4 visible at first glance:

| App | Role |
|---|---|
| `core` | health checks (`/healthz`, `/readyz`), ops trigger endpoints, SPA catch-all route |
| `leads` | models only — `Prospect` (pre-contact) → `Lead` (post-contact CRM record), via `Prospect.convert_to_lead()` |
| `scraper` | Stage-1 listing scrape (CSS-selector engine, Playwright-in-subprocess) → Stage-2 detail-page enrichment; Celery tasks; auto-discovery of platform configs |
| `crawler` | a second, independent lead pipeline: Serper/Bing domain discovery → BFS crawl → spaCy/rule-based/Gemini scoring → East-Africa-specific "active buyer" qualification → promotes into `Prospect` |
| `crm_integration` | Perfex CRM sync via REST client + Celery retry/backoff, gated by `PERFEX_SYNC_ENABLED` |
| `sheets_integration` | Google Sheets export via service account, gated by `GSHEETS_ENABLED` |
| `dashboard` | the real presentation layer: Django-template views **and** a DRF JSON API **and** SSE streaming **and** CSV export **and** session auth — everything else routes through here |

`scraper` and `crawler` are parallel, independently-evolved lead-gen pipelines feeding the same `Prospect`/`Lead` models — not a single pipeline with two stages.

## 2. What works

- Celery is fully wired: broker/backend on Redis, `docker-compose.yml` and `Procfile` both define real `web`/`worker`/`beat` services, `CELERY_BEAT_SCHEDULE` runs enqueue/sync/discovery tasks on real intervals.
- Settings are deliberately production-aware: `SECRET_KEY` default raises `RuntimeError` if used with `DEBUG=False`, HSTS/secure-cookie/SSL-redirect block, WhiteNoise, Sentry, structlog, CORS/CSRF handling for the split SPA + ngrok dev setup.
- No dead-end stub logic in business code — no `TODO`/`FIXME`/`NotImplementedError`/pass-only functions anywhere in the backend or frontend. What exists generally works end to end.
- The React frontend is clean: strict TypeScript, no console.logs/dead debug code, every page wired to real TanStack Query calls against the shared API layer, working build/lint/test scripts.
- CRM sync and Sheets export are feature-complete, just intentionally opt-in via env flags (off/on by default respectively) — not incomplete, just unconfigured out of the box.
- Test coverage is genuinely real (not stub tests) in `crawler`, `dashboard`, `crm_integration`, `scraper`, `leads`, though there's no CI config found to confirm they run automatically.

## 3. What's broken

1. **Live secrets sitting in `backend/.env` on disk.** A full Google service-account private key (project `ateric`), a Serper API key, a Gemini API key, a Django secret key, and a real Sheets spreadsheet ID are all present in plaintext. `.env` is correctly gitignored, so it isn't currently tracked — but `git-filter-repo` (a tool almost exclusively used to scrub secrets from git history after an accidental commit) is pinned in `requirements.txt`, which is a strong signal these secrets — or earlier versions of them — may already be sitting in git history. **Recommend a git-history secret scan (`trufflehog`/`gitleaks` or `git log -p -- '*.env'`) before this repo is ever pushed anywhere semi-public, and rotating all four credentials regardless.**
2. **Dead JWT auth config.** `REST_FRAMEWORK` is configured for `JWTAuthentication` and `SIMPLE_JWT`/`djangorestframework_simplejwt` are installed, but every real DRF view overrides this with `SessionAuthentication`, and there's no `/api/token/` endpoint anywhere. This configuration is inert and misleading to anyone reading settings.py expecting JWT to be live.
3. **Activity Log & Notifications are dead on arrival.** `dashboard`'s Phase 5 doc marks these "✅ Complete," but the project's own `DASHBOARD_ANALYSIS_SUMMARY.md` admits the models and helper functions (`log_activity()`, `create_notification()`) exist but are **never called** anywhere in the codebase — 0% integrated. The audit trail and notification bell are non-functional despite being marked done.
4. **`django_filters` and `django_tables2`** are installed apps with zero actual usage anywhere in the codebase — dead weight, possibly leftover from an earlier version of the dashboard before it was rebuilt around the DRF API.
5. **Migration gap**: `leads/migrations/` jumps `0002` → `0004` with no `0003` (cosmetically odd, not functionally broken — `0004` depends directly on `0002`).
6. **PyYAML gap**: `scraper/management/commands/sync_targets.py` supports YAML target configs (guarded `import yaml`), but PyYAML isn't in `requirements.txt` — will fail with a clear error, but the command's own `--help` doesn't warn about the missing dependency.
7. **Dead/orphaned frontend code**: `src/shared/api/index.ts` still exports `triggerScrape`/`getRunStatus`/`retryRun` hitting legacy `/dashboard/api/trigger-scrape/`-style URLs with zero callers anywhere in the app (superseded by the `v1/scrape-runs/...` endpoints); `src/components/admin/{crawler,scraper}-admin-{sections,subnav}.tsx` are never imported; `src/App.css` and the stock Vite logo/hero assets are unreferenced scaffold leftovers.
8. **Tech-debt inconsistency, not a bug**: `ProspectDetailPage.tsx`/`LeadDetailPage.tsx` import from `@/lib/api/dashboard`, a file explicitly marked `@deprecated` in favor of `@/shared/api/pipeline` — everywhere else correctly uses the new path.

## 4. What's missing / incomplete / overstated

- **No unit/integration test wiring visible for CI**, no rate limiting, no formal user-permission system beyond `is_staff` vs. a `scraper` group — all flagged by the project's own analysis doc, which puts overall completion at **~70%**, directly contradicting several docs' "PRODUCTION READY 🚀" language (`IMPLEMENTATION_SUMMARY.md`, the template-linting docs).
- **Only Eventbrite scraping was ever actually validated end-to-end.** Meetup/Ticketmaster/Eventful/LinkedIn/Twitter/Facebook selector support is repeatedly self-described in the docs as "template exists but untested" or "use the official API instead" — i.e., aspirational, not working, coverage.
- **Stage-2 enrichment (email/phone backfill) mostly doesn't work**, per the project's own `TWO_STAGE_SCRAPING.md`: most platforms simply don't expose contact info publicly. This is disclosed honestly in that doc, unlike the "complete" framing elsewhere.
- **No admin UI for CRM sync status.** The only frontend touchpoint for `crm_integration` is a single "sync to CRM" button on a lead; there's no visibility into sync history, errors, or field mapping from the UI (may exist server-side only, unreached by any frontend view).
- **Large swaths of `requirements.txt` are unexplained by any doc or by grep of actual usage**: a full data-viz stack (pandas/numpy/matplotlib/seaborn/plotly), ~20 `tree-sitter-*` language grammars, and `flower` (Celery monitoring UI) are all pinned dependencies with no visible connection to the lead-scraping product and no mention anywhere in the docs. Worth auditing — either dead weight bloating install time, or evidence of experiments/tooling that never got documented.
- **The React SPA's existence and its relationship to the Bootstrap dashboard is undocumented anywhere.** Which one is the maintained, current UI needs to be settled and written down.

## 5. Recommended next steps, in priority order

1. Rotate the Gemini, Serper, and Google service-account credentials currently sitting in `backend/.env`, and scan git history for prior leaks before doing anything else with this repo (push to a new remote, share it, add collaborators).
2. Decide and document which frontend is canonical (React SPA vs. Bootstrap dashboard) and archive or delete the other's code/docs accordingly.
3. Either wire up Activity Log/Notifications for real or strike the "complete" claim and remove the dead code paths.
4. Remove dead config (`django_filters`, `django_tables2`, unused JWT settings) and dead frontend files (`App.css`, unused assets, orphaned `admin/*-sections.tsx` components, legacy `triggerScrape`/`getRunStatus`/`retryRun` API functions) to cut noise for future contributors.
5. Add PyYAML to `requirements.txt` if YAML target configs are meant to be supported, or remove that code path if not.
6. Prune `requirements.txt` of anything not actually imported (data-viz stack, tree-sitter grammars) unless there's a planned use — confirm with whoever added them first, since removing live dependencies blindly could break something not caught by grep (e.g. dynamic imports).
7. Add a short root-level architecture doc that supersedes the scattered phase/fix summaries — the current 22-file doc set is hard to trust as a single source of truth given the internal contradictions found above.

---
*Methodology: three parallel deep-reads covered every real source file in `backend/` (7 Django apps, Celery config, management commands, ad hoc debug scripts), every real source file in `frontend/src` (135 files), and all 22 backend markdown docs plus `requirements.txt`/`docker-compose.yml`/`Procfile`/`.env`. Vendored/generated trees (`backend/venv`, `backend/staticfiles`, `frontend/node_modules`, `.git`) were excluded from the read.*
