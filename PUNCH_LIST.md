# Cross-Feature Punch List
*Generated 2026-07-20 — consolidates [AI_SEARCH_ANALYSIS.md](AI_SEARCH_ANALYSIS.md), [CRAWLER_ANALYSIS.md](CRAWLER_ANALYSIS.md), [SCRAPER_ANALYSIS.md](SCRAPER_ANALYSIS.md)*

Full detail, file:line references, and ~70 additional lower-priority findings live in the three source reports. This file orders the ones worth doing next.

## Done

- [x] **Crawler run-status race** — `discover_websites_task` marked its `CrawlRun` `SUCCESS` before any queued `crawl_domain_task` ran, causing every domain in a scheduled run to self-abort via `_run_is_cancelled`. Fixed in `backend/crawler/tasks.py` with proper completion tracking (`_finalize_crawl_run_if_complete`) driven off `CrawlRunDomainResult` terminal states; also fixes manually-triggered crawls never reaching a terminal status (same root cause). 4 regression tests added, 44/44 crawler tests pass.

## P0 — Silent breakage of core functionality / security exposure

1. **Scraper: wizard-created targets silently drop every scraped title and date.** Auto-detected platform configs use field keys (`full_name`, `event_date`) that `upsert.py`'s mapping never reads — runs "succeed," Prospects get created, but with blank titles/dates, for every platform the wizard supports. *(SCRAPER_ANALYSIS.md #1)*
2. **Scraper: SSRF — no host validation on `start_url` anywhere.** Any user in the `scraper` group (not just admins) can point a target at `localhost`/RFC1918/cloud-metadata addresses and read the response back through their own Prospect records. Same gap in `/ops/auto-create-target`. *(SCRAPER_ANALYSIS.md #8)*
3. **Scraper: manual "Run Scrape" bypasses the concurrency guard entirely**, and timed-out Playwright subprocesses leave zombie Chromium processes on Windows (no child-tree cleanup) — repeated manual triggers can pile up unkillable browser processes on the worker host. *(SCRAPER_ANALYSIS.md #5, #7)*
4. **AI search: prompt injection into the qualification LLM.** Raw scraped page text (up to 24k chars) is spliced directly into the Gemini extraction prompt with no injection defense, and the model's output directly gates lead promotion — a crafted page can force a bogus lead through. *(AI_SEARCH_ANALYSIS.md #12)*
5. **AI search: promotion is a TOCTOU race with no DB backstop** — duplicate-check-then-create with no `select_for_update`/unique constraint; two near-simultaneous promotes of the same result can create two `Prospect` rows. Crawler's `EventProspect` has the identical gap (no unique constraint, concurrent `analyze_domain_task` runs can double-create). *(AI_SEARCH_ANALYSIS.md #5, CRAWLER_ANALYSIS.md #10)*
6. **Crawler: scheduled runs can overwrite another user's Prospect.** `create_or_update_prospect` only scopes dedup by owner `if owner_id:` — but scheduled runs always pass `owner_id=None`, so dedup searches all owners unfiltered. Scraper has the identical pattern for null-owner (system-provisioned) targets. *(CRAWLER_ANALYSIS.md #7, SCRAPER_ANALYSIS.md #17)*

## P1 — Real correctness bugs, resource/cost risk

7. **Crawler: one failed page marks an entire domain crawl `failed`**, even when nearly everything succeeded — the `error` variable is never cleared on a later success. Compounds with #8. *(CRAWLER_ANALYSIS.md #3)*
8. **Crawler: failed domains are never retried**; `next_attempt_at` exists on the model and is indexed but is never written anywhere. Configured Celery `max_retries`/`default_retry_delay` on all three crawler tasks are dead code — nothing ever calls `self.retry()`. *(CRAWLER_ANALYSIS.md #4, #5)*
9. **Scraper: the opposite problem — failed targets retry forever with no backoff or auto-disable**, spamming notifications/activity-log on every beat tick indefinitely. *(SCRAPER_ANALYSIS.md #4)*
10. **AI search: admin job-creation config check doesn't match the task's actual requirement** — admin path ignores `AI_SEARCH_REQUIRE_GEMINI`, so a job can be accepted (201) then instantly fail. *(AI_SEARCH_ANALYSIS.md #3)*
11. **AI search: no LLM-cost-specific rate limiting** — a single job can trigger 40+ Gemini calls, only throttled by a generic 120/min request limit; frontend only disables submit for the POST's duration, not while a job is actually running. *(AI_SEARCH_ANALYSIS.md #13, frontend #11)*
12. **Crawler: the entire ad-hoc "Discover" workflow frontend calls backend endpoints that don't exist** (`/dashboard/api/crawler/preview/`, `/crawler/queue/` — zero matches anywhere in the backend). Every action on `CrawlerDiscoverPage` 404s. *(CRAWLER_ANALYSIS.md #11)*
13. **No error state anywhere in any of the three features' frontends** — every failed list/detail fetch (AI search, crawler, scraper, staff and admin) renders as "no data" rather than an error, indistinguishable from a legitimately empty result. Same root pattern across ~15 individual pages/components. *(all three reports)*
14. **Crawler: rate-limit config is computed and stored but never applied** — `CRAWLER_RATE_LIMIT_SECONDS` is ignored, `crawler.py` always uses a hardcoded constant; the discovery-time qualification fetch (`discovery_qualify.py`) has no robots.txt check or rate limiting at all, unlike the BFS crawler. *(CRAWLER_ANALYSIS.md #8, #9)*
15. **AI search: `prospects_created` field is always 0** — defined, serialized to the frontend, never written anywhere (unlike the equivalent field on `CrawlRun`, which is correctly incremented). *(AI_SEARCH_ANALYSIS.md #1)*
16. **Scraper: N/A — Playwright timeout double-budget** — `page.goto`/`page.wait_for_selector` can each consume the full configured timeout while the outer subprocess budget assumes only one will, causing hard failures instead of graceful partial-content returns. *(SCRAPER_ANALYSIS.md #6)*

## P2 — Data quality, dead code, tech debt, coverage gaps

Grouped by feature; see source reports for file:line detail.

**AI search**: N+1 on non-admin job list (missing `select_related`); no idempotency guard if a job message is redelivered; email-based promotion dedup can merge unrelated organizations sharing a generic inbox; `EventProspect.ai_search_result` FK defined but never populated; zero test coverage for the actual Celery task or API layer; frontend field-level form validation never fires (no resolver wired to `useForm`); recent-jobs list goes stale during a run (no `refetchInterval`); operational debug text leaks to non-admin staff.

**Crawler**: domains can get stuck at `crawl_status="crawling"` forever if a worker dies mid-crawl, no sweep exists; "Running now" stat on staff dashboard undercounts (samples only 10 most-recent runs) vs. admin's correct dedicated count query; `StatusBadge`'s `kind` prop is dead/misleading; no CrawlSource create/delete UI or API exists at all (only PATCH); duplicated non-shared stats-card implementations already drifted (staff polls, admin doesn't); a working SSE stream exists but crawler pages don't use it, polling instead; dead/orphaned `components/admin/{crawler,scraper}-admin-*` files confirmed still present; zero test coverage for the BFS crawl, any Celery task, or crawler dashboard API endpoints; **test-isolation gap found while fixing #1's regression tests: `crawler/migrations/0002_seed_sources_and_target.py` seeds real, enabled `CrawlSource` rows with live discovery queries into every fresh DB including the test DB — any test that runs `discover_websites_task` without explicitly disabling them will make real Serper/HTTP calls (confirmed: one such run took 6+ minutes hitting live external sites before this was caught).**

**Scraper**: dedup falls back to a fragile whole-payload hash almost every time (Stage-1 listings rarely have email/phone); Stage-2 enrichment skip condition too broad (skips on `company` alone, leaving other fields unenriched); no server-side config schema validation (client-only); staff vs admin UI capability drift (admin has strictly less filtering); confirmed-dead legacy API exports (`triggerScrape`/`getRunStatus`/`retryRun`) and orphaned `scraper-admin-*` component files; target-edit form silently discards unsaved edits on an unrelated background refetch; wizard's URL-assistant field doesn't sync on load (stuck blank until user retypes); target/run lists silently cap at 200 with no truncation indicator; `run_every_minutes: 0` silently becomes 60 instead of clamping to 1.

## Suggested order

1. Fix #1 (scraper field-mapping) and #2 (SSRF) together — both are high-severity, both isolated to `backend/scraper/`, and #1 is likely why lead quality/volume looks worse than expected from this pipeline.
2. Fix #3 (scraper concurrency/zombie processes) — same file area as #1/#2, and directly reduces production risk (resource exhaustion).
3. Address #4–#6 (AI search prompt injection + both promotion races) as one pass — all are "a bad actor or a double-click corrupts the lead pipeline" class bugs.
4. Then work down P1 in order; P2 items are good candidates to fix opportunistically while touching nearby code, or to batch into a dedicated cleanup pass.
