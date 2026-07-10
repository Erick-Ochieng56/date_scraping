# Crawl & Scrape Scheduling — Implementation Plan

**Status:** Draft  
**Last updated:** July 2026  
**Audience:** Engineering (backend, frontend, ops)  
**Related docs:** `frontend/rework.md`, `backend/HOW_TO_RUN.md`, `backend/DASHBOARD_PHASE5_COMPLETE.md`

---

## 1. Summary

Operators need to **control when and how long** the crawler (and optionally the scraper) runs — not only one-shot manual triggers or global env intervals. The primary ask:

> Start a crawl now and keep discovering + crawling for a chosen window (30 minutes → 24 hours), then **stop automatically** and **notify** the user.

Secondary asks:

- **Recurring schedules** (e.g. every 12 hours, or daily 6-hour sessions)
- **Notifications** for session start, progress milestones, completion, failure, and cancellation
- **UI** on the React dashboard (staff + admin) to configure and monitor active sessions

This document is the full implementation plan: current state, target architecture, API contract, UI, phases, tests, and rollout.

---

## 2. Goals & non-goals

### Goals

| # | Goal |
|---|------|
| G1 | User can start a **crawl session** with a duration preset (30m, 1h, 3h, 6h, 12h, 24h) or custom minutes |
| G2 | Session **auto-stops** at `ends_at`; in-flight domain tasks respect the deadline |
| G3 | User can **cancel early** (existing cancel API extended for sessions) |
| G4 | **Notifications** fire on session start, end, failure, and optional progress summaries |
| G5 | **Active session** visible on Crawler home + run detail (time remaining, domains processed) |
| G6 | One active session per user (or global policy — see §8.3) to avoid runaway load |
| G7 | Scraper **interval scheduling** remains supported; document parity with crawl sessions |

### Non-goals (v1)

- Cron-style “every Tuesday at 3am” (use Phase 3 recurring + future crontab)
- Per-domain duration limits (session is run-level only)
- Push notifications / email / Slack (in-app bell only)
- Resume a paused session (cancel + start new is sufficient for v1)
- Replacing Celery Beat global `CRAWLER_DISCOVERY_INTERVAL_SECONDS` (sessions are additive)

---

## 3. Current state (audit)

### 3.1 Scraper

| Piece | Location | Behavior |
|-------|----------|----------|
| Per-target interval | `ScrapeTarget.run_every_minutes` | Default 60; UI in `TargetFormPage`, `TargetWizardPanel` |
| Beat checker | `scraper.tasks.enqueue_enabled_targets` | Every `SCRAPE_ALL_INTERVAL_SECONDS` (default 300s) |
| Manual trigger | `POST /dashboard/api/v1/targets/<id>/trigger/` | One-shot scrape |
| Notifications | `scraper.tasks.scrape_target` | `create_notification_for_all_users` on success/fail |
| Run model | `ScrapeRun` | `started_at`, `finished_at`, `trigger` = scheduled \| manual |

**Gap:** No “scrape for 6 hours” session — only recurring per-target or one-shot manual.

### 3.2 Crawler

| Piece | Location | Behavior |
|-------|----------|----------|
| Global beat | `leads_app/settings.py` → `discover_websites_task` | `CRAWLER_DISCOVERY_INTERVAL_SECONDS` (default 43200 = 12h) |
| Manual trigger | `POST /dashboard/api/v1/crawl-runs/trigger/` | One discovery cycle; no duration |
| Sources | `CrawlSource` | `enabled`, `priority` — **no** `run_every_minutes` |
| Cancel | `crawl_run_cancel`, `crawl_runs_cancel_all` | Sets run `FAILED` + `error_text`; workers check `_run_is_cancelled` |
| Notifications | — | **None** for crawler |
| Run lifecycle | `discover_websites_task` | Marks run `SUCCESS` when discovery finishes, **while domain tasks may still run** |

**Gaps:**

1. No user-chosen duration or `ends_at`
2. No coordinator to loop discovery/crawl until deadline
3. Run status misleading for long multi-domain work
4. No crawl notifications
5. No UI for scheduling beyond “Run scheduled discovery” button (`CrawlerHomePage`)

### 3.3 Notifications (shared)

| Piece | Location | Behavior |
|-------|----------|----------|
| Model | `dashboard.models.Notification` | Per-user, types info/success/warning/error |
| Helpers | `dashboard.utils.create_notification`, `create_notification_for_all_users` | Used by scraper only |
| API | `GET /dashboard/api/v1/notifications/`, `POST .../read/` | Staff SPA |
| UI | `NotificationBell.tsx` | Polls every 30s |

### 3.4 Infrastructure prerequisites

- **Redis** + **Celery worker** + **Celery Beat** must be running (`backend/HOW_TO_RUN.md`)
- Without Beat, only manual/session triggers work; global discovery interval disabled if `CRAWLER_ENABLED=0`

---

## 4. User stories

### Crawl sessions (P0)

1. **As staff**, I open Crawler home and choose “Start crawl session → 6 hours” so discovery and crawling continue until the window closes.
2. **As staff**, I see **time remaining** and domains crawled / prospects created on the active session card.
3. **As staff**, I receive a **notification** when the session starts and when it ends (with summary stats).
4. **As staff**, I can **Stop session** early; queued work stops and I get a cancellation notification.
5. **As admin**, I can see all users’ active sessions and cancel them.

### Recurring crawl (P1)

6. **As staff**, I set a crawl source (or global policy) to **repeat every N hours** without starting each session manually.
7. **As staff**, I optionally combine recurring + duration: “Every 12 hours, run a 2-hour session.”

### Scrape sessions (P2)

8. **As staff**, I start a **scrape session** for 12 hours that keeps enqueueing due enabled targets on their intervals within the window.

### Notifications (P0)

9. **As staff**, crawl events appear in the **notification bell** with links to the run detail page.
10. **As staff**, long sessions (≥6h) send an optional **mid-session summary** every 2 hours.

---

## 5. Concepts & terminology

| Term | Definition |
|------|------------|
| **Session** | A bounded run with `started_at`, `ends_at`, and `duration_minutes`. Parent container for work. |
| **Cycle** | One discovery burst + enqueue of pending domains inside a session. Repeats until `ends_at`. |
| **One-shot run** | Today’s `discover_websites_task` — single discovery, no duration. Kept for backwards compatibility. |
| **Scheduled (beat)** | Celery Beat global task — unchanged unless Phase 3 adds per-source intervals. |
| **Trigger** | `manual` \| `scheduled` \| `session` (new) on `CrawlRun` |

---

## 6. Target architecture

### 6.1 High-level flow

```
User picks duration (e.g. 6h)
        │
        ▼
POST /crawl-sessions/  ──► CrawlRun created (trigger=session, ends_at=now+6h)
        │                    notify: "Session started"
        ▼
crawl_session_coordinator_task (loop)
        │
        ├─ while now < ends_at and status=running:
        │     ├─ discover_websites (enabled sources)
        │     ├─ enqueue pending domains (cap per cycle)
        │     └─ sleep(cycle_interval)  e.g. 5–15 min
        │
        ▼
ends_at reached OR user cancel
        │
        ├─ mark session completed/cancelled
        ├─ revoke coordinator task
        └─ notify: summary stats
```

Domain workers (`crawl_domain_task`, `analyze_domain_task`, `score_and_create_prospect_task`) already call `_run_is_cancelled(run_id)` — extend checks to also treat `now >= ends_at` as stopped.

### 6.2 Why extend `CrawlRun` vs new model

**Recommendation:** Extend `CrawlRun` first (fewer joins, existing UI lists runs).

Add fields:

```python
# crawler/models.py — CrawlRun additions
ends_at = models.DateTimeField(null=True, blank=True)
duration_minutes = models.PositiveIntegerField(null=True, blank=True)
session_mode = models.BooleanField(default=False)  # or infer from trigger=session
coordinator_task_id = models.CharField(max_length=255, blank=True, default="")
cycles_completed = models.PositiveIntegerField(default=0)
last_cycle_at = models.DateTimeField(null=True, blank=True)
```

Add trigger choice:

```python
class CrawlRunTrigger(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    MANUAL = "manual", "Manual"
    SESSION = "session", "Session"  # new
```

**Alternative (Phase 2+):** `CrawlSession` 1:1 with `CrawlRun` if session metadata grows (recurring rules, user prefs).

### 6.3 Session coordinator task

New Celery task: `crawl_session_coordinator_task(run_id: int)`

Responsibilities:

1. Load run; exit if cancelled or past `ends_at`
2. Run discovery logic (extract from `discover_websites_task` or call shared `run_discovery_cycle`)
3. Enqueue `crawl_domain_task` for pending domains up to `min(max_domains_per_cycle, env cap)`
4. Increment `cycles_completed`, set `last_cycle_at`
5. Schedule self again with `countdown=cycle_interval_seconds` **or** loop with sleep inside task (prefer **re-queue self** so workers aren’t blocked for hours)
6. On final cycle / deadline: call `finalize_crawl_session(run_id, reason="completed"|"cancelled"|"deadline")`

Schedule deadline handler:

```python
finalize_crawl_session.apply_async(args=[run_id], eta=run.ends_at)
```

Backup: Beat task every 60s `sweep_expired_crawl_sessions` for missed ETAs.

### 6.4 Stopping semantics

| Event | Run status | `finished_at` | Worker behavior |
|-------|------------|---------------|-----------------|
| Deadline reached | `success` | now | `_run_is_stopped`: skip new work |
| User cancel | `failed` (or new `cancelled`) | now | Same as today |
| Coordinator error | `failed` | now | Notify error |
| Exception in domain task | domain failed; session continues | — | — |

Consider adding `CrawlRunStatus.CANCELLED` (optional) to distinguish user cancel vs real failure.

### 6.5 Throughput & safety caps

Env vars (with session overrides in `run.config`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `CRAWLER_SESSION_MAX_DOMAINS_PER_CYCLE` | 50 | Domains enqueued per coordinator cycle |
| `CRAWLER_SESSION_CYCLE_INTERVAL_SECONDS` | 600 | 10 min between discovery cycles |
| `CRAWLER_SESSION_MAX_ACTIVE_PER_USER` | 1 | Prevent parallel sessions |
| `CRAWLER_MAX_DOMAINS_PER_RUN` | 500 | Existing global cap (still apply) |
| `CRAWLER_RATE_LIMIT_SECONDS` | 1.5 | Per-domain throttle |

**Rough capacity (order of magnitude):**

- 6h session, 10 min cycles → ~36 cycles
- 50 domains/cycle → up to ~1,800 domains enqueued (subject to queue depth and worker speed)
- 24h at same rate → ~7,200 domains — may need lower cycle cap or longer interval on small deployments

Document in admin/settings read-only display.

---

## 7. API design

### 7.1 New endpoints (staff v1)

Base: `/dashboard/api/v1/`

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `crawl-sessions/` | `{ "duration_minutes": 360 }` or `{ "preset": "6h" }` | `{ run_id, ends_at, message }` |
| `GET` | `crawl-sessions/active/` | — | Current user’s active session or `null` |
| `POST` | `crawl-sessions/<run_id>/stop/` | — | Same as cancel; alias for UX |
| `GET` | `crawl-runs/<id>/` | — | **Extend** serializer with `ends_at`, `duration_minutes`, `time_remaining_seconds`, `cycles_completed` |

Presets (server-side map):

```json
{
  "30m": 30,
  "1h": 60,
  "3h": 180,
  "6h": 360,
  "12h": 720,
  "24h": 1440
}
```

Custom: `duration_minutes` 15–1440 (clamp); validate in serializer.

### 7.2 Existing endpoints (behaviour)

| Endpoint | Change |
|----------|--------|
| `POST crawl-runs/trigger/` | Unchanged — one-shot discovery (no duration) |
| `POST crawl-runs/<id>/cancel/` | Works for sessions; set `error_text` = "Cancelled by user" |
| `GET crawl-runs/` | Filter `trigger=session`; show session fields |

### 7.3 Admin v1

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `admin/v1/crawl-sessions/active/` | All active sessions |
| `POST` | `admin/v1/crawl-sessions/<run_id>/stop/` | Admin cancel |

### 7.4 Serializer changes

`CrawlRunSerializer` additions:

```python
ends_at
duration_minutes
trigger  # includes "session"
cycles_completed
last_cycle_at
time_remaining_seconds  # computed read-only
is_session_active       # computed: status=running and ends_at > now
```

### 7.5 Frontend API (`shared/api/crawler.ts`)

```typescript
export type CrawlSessionPreset = '30m' | '1h' | '3h' | '6h' | '12h' | '24h'

export async function startCrawlSession(body: { duration_minutes?: number; preset?: CrawlSessionPreset })
export async function getActiveCrawlSession()
export async function stopCrawlSession(runId: number)
```

---

## 8. Notifications

### 8.1 Events

| Event | Type | Title example | Recipient |
|-------|------|---------------|-----------|
| Session started | info | Crawl session started (6h) | initiating user (+ optional all staff) |
| Session completed | success | Crawl session finished — 84 domains, 12 prospects | initiating user |
| Session cancelled | warning | Crawl session stopped early | initiating user |
| Session failed | error | Crawl session failed | initiating user |
| Progress (optional) | info | Crawl session update — 2h elapsed, 40 domains | initiating user |

Use `create_notification(user=initiator, ...)` for sessions; keep `create_notification_for_all_users` for global scrape events only.

`link_url`: `/crawler/runs/{id}` (SPA route).

### 8.2 Implementation

New helper: `dashboard/utils.py`

```python
def notify_crawl_session(user, run, event: str) -> None:
    ...
```

Call from:

- `crawl_session_coordinator_task` (start, progress, finalize)
- `crawl_run_cancel` when `run.trigger == SESSION`

### 8.3 Progress notifications (long sessions)

If `duration_minutes >= 360` (6h), schedule periodic summary:

- Every 120 minutes while running
- Store `last_progress_notification_at` on run or in `stats` JSON to avoid spam

### 8.4 Frontend

- `NotificationBell`: fix link routes to use React paths (some scrape links may still say `/dashboard/runs/`)
- Optional: toast on SSE/poll when active session ends (home page already polls runs every 5s)

---

## 9. Frontend UI

### 9.1 Crawler home (`CrawlerHomePage.tsx`)

Replace single “Run scheduled discovery” with:

```
┌─────────────────────────────────────────────────┐
│ Crawl session                                    │
│ [ Preset ▼ 6 hours ]  [ Start session ]         │
│ Active: ends 8:49 PM · 2h 14m left · Run #42    │
│ [ Stop session ]                                 │
└─────────────────────────────────────────────────┘
│ Quick actions                                    │
│ [ One-shot discovery ]  (existing trigger)       │
└─────────────────────────────────────────────────┘
```

Components to add:

- `CrawlSessionPanel.tsx` — preset select, start/stop, active session card
- `crawlSessionPresets.ts` — labels + minutes map

### 9.2 Crawl run detail (`CrawlerRunDetailPage.tsx`)

For `trigger === 'session'`:

- Show duration, `ends_at`, time remaining (live countdown via `setInterval`)
- Cycles completed, last cycle time
- Progress bar: `elapsed / duration`

### 9.3 Crawl runs list (`CrawlerRunsPage.tsx`)

- Badge: “Session” for `trigger=session`
- Column or subtitle: “6h · ends 8:49 PM”

### 9.4 Admin

- Active sessions table on `AdminCrawlerOpsPage` or monitoring
- Cancel action per row

### 9.5 Scraper (Phase 2)

- Optional `ScrapeSessionPanel` on scraper home mirroring crawl UX
- Or document that `run_every_minutes` covers recurring scrape needs

---

## 10. Scraper scheduling (Phase 2 — optional)

If product requires **scrape for N hours**:

1. Add `ScrapeSession` or extend `ScrapeRun` with `ends_at`
2. Coordinator enqueues `enqueue_enabled_targets` logic on an interval while `now < ends_at`
3. Reuse notification patterns

**Lower priority** — per-target `run_every_minutes` already covers most scrape scheduling; align with stakeholders before building.

---

## 11. Recurring crawl schedules (Phase 3)

### 11.1 Model

```python
class CrawlSchedule(models.Model):
    owner = models.ForeignKey(User, ...)
    name = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    interval_minutes = models.PositiveIntegerField()  # e.g. 720 = 12h
    session_duration_minutes = models.PositiveIntegerField(null=True)  # optional cap per run
    last_started_at = models.DateTimeField(null=True)
    source_filter = models.JSONField(default=dict)  # optional: limit sources
```

### 11.2 Beat task

`enqueue_due_crawl_schedules` every 5 minutes:

- If `enabled` and `(now - last_started_at) >= interval` and no active session for user → `start_crawl_session(duration=session_duration_minutes or default)`

### 11.3 UI

- `/crawler/schedules` — CRUD list (staff: own; admin: all)
- Link from Crawler home

---

## 12. Database migrations

1. `crawler/migrations/XXXX_crawlrun_session_fields.py`
   - `ends_at`, `duration_minutes`, `coordinator_task_id`, `cycles_completed`, `last_cycle_at`
   - `CrawlRunTrigger.SESSION`
2. (Phase 3) `CrawlSchedule` table
3. (Phase 2 optional) `CrawlRunStatus.CANCELLED`

**Backfill:** Existing runs leave new fields null; `trigger` unchanged.

---

## 13. Implementation phases

### Phase 0 — Prerequisites (0.5 day)

- [ ] Confirm Celery worker + Beat running in staging/prod
- [ ] Document env caps in admin settings page (read-only)
- [ ] Fix notification `link_url` paths for SPA where needed

### Phase 1 — Crawl sessions core (3–5 days)

**Backend**

- [ ] Migration: session fields on `CrawlRun`
- [ ] `CrawlRunTrigger.SESSION`
- [ ] Refactor: `run_discovery_cycle(owner_id, run_id) -> stats` extracted from `discover_websites_task`
- [ ] `crawl_session_coordinator_task`
- [ ] `finalize_crawl_session` + ETA task at `ends_at`
- [ ] `sweep_expired_crawl_sessions` beat task (60s)
- [ ] Extend `_run_is_cancelled` → `_run_is_stopped` (cancelled OR past `ends_at`)
- [ ] `POST /crawl-sessions/`, `GET /crawl-sessions/active/`
- [ ] Extend `CrawlRunSerializer`
- [ ] Tests: start session, deadline stop, early cancel, one active session limit

**Frontend**

- [ ] API client functions
- [ ] `CrawlSessionPanel` on `CrawlerHomePage`
- [ ] Run detail session UI
- [ ] Runs list session badge

**Notifications**

- [ ] `notify_crawl_session` on start / end / cancel / fail

**Acceptance**

- User starts 30m session; it stops automatically; notification received; run detail shows session metadata

### Phase 2 — Long sessions & polish (2–3 days)

- [ ] Presets through 24h + custom minutes validation
- [ ] Progress notifications every 2h for sessions ≥6h
- [ ] Admin active sessions view + cancel
- [ ] Load testing notes / tune `CRAWLER_SESSION_*` defaults
- [ ] Update `HOW_TO_RUN.md` and `rework.md`

### Phase 3 — Recurring schedules (3–4 days)

- [ ] `CrawlSchedule` model + CRUD API
- [ ] `enqueue_due_crawl_schedules` beat task
- [ ] `/crawler/schedules` UI
- [ ] Tests: schedule fires session, doesn’t double-start

### Phase 4 — Scrape sessions (optional, 2–3 days)

- [ ] Only if stakeholders confirm need beyond `run_every_minutes`
- [ ] Mirror crawl session pattern for scraper

---

## 14. Testing plan

### Unit tests

| Area | Cases |
|------|-------|
| Serializer | Preset mapping, clamp 15–1440, reject active duplicate |
| `_run_is_stopped` | running + before ends_at → false; after ends_at → true |
| Coordinator | One cycle enqueues domains; respects cap; re-queues self |

### Integration tests (`dashboard/tests.py`)

| Test | Steps |
|------|-------|
| `test_start_crawl_session` | POST session 60m → run created, `ends_at` set, coordinator task id |
| `test_active_session_conflict` | Second POST while active → 400 |
| `test_cancel_session` | POST cancel → workers skip; notification created |
| `test_session_serializer_fields` | GET run includes `time_remaining_seconds` |

### Manual QA checklist

- [ ] Start 30m session on staging; verify auto-stop
- [ ] Cancel at 5m; no new domains enqueued after cancel
- [ ] Notification bell shows start + end with working link
- [ ] 6h session shows countdown on run detail
- [ ] Beat + worker restart mid-session: sweep task finalizes expired runs

---

## 15. Operations & deployment

### Env vars (add to `.env.example`)

```bash
# Crawl sessions
CRAWLER_SESSION_ENABLED=1
CRAWLER_SESSION_MAX_DOMAINS_PER_CYCLE=50
CRAWLER_SESSION_CYCLE_INTERVAL_SECONDS=600
CRAWLER_SESSION_MAX_ACTIVE_PER_USER=1
CRAWLER_SESSION_MIN_DURATION_MINUTES=15
CRAWLER_SESSION_MAX_DURATION_MINUTES=1440
CRAWLER_SESSION_PROGRESS_NOTIFY_MINUTES=120
```

### Rollout

1. Deploy backend with `CRAWLER_SESSION_ENABLED=0` (dark launch)
2. Enable in staging; run 30m test session
3. Enable in prod; announce to operators
4. Monitor Redis queue depth, worker CPU, domain failure rate

### Rollback

- Set `CRAWLER_SESSION_ENABLED=0` — API returns 503 or ignores POST
- Existing one-shot `crawl-runs/trigger/` unchanged

---

## 16. Open questions

| # | Question | Recommendation |
|---|----------|----------------|
| Q1 | One active session per **user** or **global**? | Per user (default); admin override to cancel others |
| Q2 | Session discovery: all enabled sources or user-selected? | v1: all enabled (same as today); v2: source multiselect |
| Q3 | Status `cancelled` vs `failed` for user stop? | Add `cancelled` for clearer UX |
| Q4 | Notify only initiator or all staff? | Initiator only for sessions; all staff for scrape |
| Q5 | Replace global 12h beat with per-user schedules? | Keep both; schedules optional in Phase 3 |

---

## 17. File touch list (Phase 1)

| File | Change |
|------|--------|
| `backend/crawler/models.py` | Session fields, trigger |
| `backend/crawler/tasks.py` | Coordinator, finalize, refactor discovery |
| `backend/crawler/migrations/` | New migration |
| `backend/leads_app/settings.py` | Beat: sweep task |
| `backend/dashboard/api/views.py` | Session endpoints |
| `backend/dashboard/api/urls.py` | Routes |
| `backend/dashboard/api/serializers.py` | CrawlRun fields |
| `backend/dashboard/utils.py` | `notify_crawl_session` |
| `backend/dashboard/tests.py` | Session tests |
| `frontend/src/shared/api/crawler.ts` | API |
| `frontend/src/shared/api/types.ts` | Types |
| `frontend/src/features/crawler/CrawlSessionPanel.tsx` | New |
| `frontend/src/features/crawler/CrawlerHomePage.tsx` | Integrate panel |
| `frontend/src/features/crawler/CrawlerRunDetailPage.tsx` | Session UI |
| `frontend/src/features/crawler/CrawlerRunsPage.tsx` | Session badge |
| `backend/HOW_TO_RUN.md` | Session docs |
| `frontend/rework.md` | Mark feature planned → done |

---

## 18. Acceptance criteria (Phase 1 complete)

1. Staff can start a crawl session with presets **30m, 1h, 3h, 6h, 12h, 24h** from Crawler home.
2. Session auto-stops at `ends_at`; run detail shows final stats.
3. Staff can stop early; no new domains enqueue after stop.
4. Initiator receives in-app notifications for **start** and **end/cancel**.
5. Only one active session per user at a time.
6. Existing one-shot “discovery” trigger still works unchanged.
7. Backend tests cover start, stop, and deadline paths.
8. `npm run build` and `python manage.py test dashboard crawler` pass.

---

## 19. Timeline estimate

| Phase | Effort | Calendar (1 dev) |
|-------|--------|------------------|
| Phase 0 | 0.5 d | Day 1 |
| Phase 1 | 3–5 d | Days 1–6 |
| Phase 2 | 2–3 d | Days 7–9 |
| Phase 3 | 3–4 d | Days 10–14 |
| Phase 4 (optional) | 2–3 d | TBD |

**Total to production-ready crawl sessions (Phases 0–2):** ~1.5–2 weeks.  
**Full recurring schedules (Phase 3):** +1 week.

---

*End of plan.*
