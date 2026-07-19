# AI Search Feature — Full-Stack Analysis
*Generated 2026-07-19*

## 1. How it works, end to end

**Backend** (`backend/crawler/`): a user (staff or admin) submits a seed topic (+ optional industry/region) via `POST /dashboard/api/v1/ai-search/jobs/` or the admin equivalent. This creates an `AISearchJob` row (`crawler/models.py:268`) and queues `run_ai_search_job` (`crawler/tasks.py`) on Celery. The task:

1. Generates search queries from the seed topic via Gemini (`crawler/services/ai_search.py`).
2. Runs grounded web searches (Serper) for each query.
3. For each discovered domain, fetches the page and runs Gemini extraction (`crawler/services/ai_page_extract.py`) plus rule-based qualification (`crawler/services/active_buyer.py`, `discovery_qualify.py`) to score it (`translation_need_score`, `is_competitor`, `is_directory`, `has_active_procurement`, contact info).
4. Persists each qualifying domain as an `AISearchResult` (`crawler/models.py:304`), linked to the job.
5. The job transitions `pending → generating → searching → done`/`failed`; `qualification_log` and `domains_discovered` track progress.
6. A user reviews results and promotes selected ones into `leads.Prospect` via `crawler/services/promote_ai_result.py`.

**Frontend** (`frontend/src/features/ai-search/AiSearchPage.tsx`): a single implementation shared by both the staff route (`/crawler/ai-search`) and admin route (`/admin/ai-search`), parameterized by a `variant` prop. `frontend/src/pages/staff/AiSearchPage.tsx` is a one-line re-export to it (part of the repo's documented migration pattern) — **not** dead code or a stale fork. The page has a submission form, a recent-jobs table, and a job-detail panel that polls every 3s (falling back to 15s after 12 minutes) while a job is in a non-terminal state, showing per-domain results with a promote action.

## 2. Confirmed bugs

### Backend

1. **`AISearchJob.prospects_created` is dead — always 0.** The field is defined and serialized to the frontend, but nothing ever writes to it anywhere in the codebase (`crawler/models.py:294`; contrast with `CrawlRun.prospects_created`, a different model, which *is* incremented in `crawler/tasks.py:429-430`). Any UI reporting "prospects created" per job is always wrong.

2. **Gemini extraction budget undercounts real API calls.** `crawler/tasks.py:577` only decrements the local `AI_SEARCH_MAX_GEMINI_EXTRACTS` counter (default 12) when `enriched.get("extraction")` is truthy. When Gemini returns unparseable JSON, `extract_prospect_from_page` (`crawler/services/ai_page_extract.py:138-143`) returns `{}` — falsy — so a real (possibly 3×-retried) API call isn't counted. More actual Gemini calls than the configured cap can occur per job.

3. **Admin job-creation config check doesn't match the task's actual requirement.** `dashboard/api/admin_views.py:789` accepts a job as long as *either* `SERPER_API_KEY` or `GEMINI_API_KEY` is set, ignoring `AI_SEARCH_REQUIRE_GEMINI`. The non-admin path (`dashboard/api/views.py:614-619`) checks this setting correctly. With defaults (`AI_SEARCH_REQUIRE_GEMINI=True`) and only `SERPER_API_KEY` configured, an admin sees their job accepted (HTTP 201) and then it dies instantly in `run_ai_search_job` (`crawler/tasks.py:505-512`) with no way to have known upfront.

4. **No duplicate-prevention at the DB layer for `AISearchResult`, and no idempotency guard on the task.** Unlike the sibling model `CrawlRunDomainResult` in the same file (`crawler/models.py:245-257`), which has `unique_together` on `(run, domain)`, `AISearchResult` (`crawler/models.py:304-327`) has no such constraint on `(job, domain)`. Two concrete paths produce duplicates/races:
   - The admin `rerun_job` action (`crawler/admin.py:176-185`) resets status to `pending` and re-queues `run_ai_search_job.delay(job.id)` **without checking if the job is already running** — a second concurrent execution over the same job is possible.
   - `CELERY_TASK_ACKS_LATE=True` + a 330s task time limit (`leads_app/settings.py:464-465`, `crawler/tasks.py:458`) means a hard-killed worker's message can be redelivered later; `run_ai_search_job` never checks `if job.status == "done": return` at the top, so a redelivered message can reprocess a finished job and race on `status`/`qualification_log`/`domains_discovered` (last writer wins).

5. **Promotion is a TOCTOU race with no DB backstop.** `crawler/services/promote_ai_result.py:31-111` checks for existing prospects via plain `.filter().first()` calls (by `promoted_prospect_id`, `email`, `website`, `raw_payload_hash`) with no `select_for_update()`/`transaction.atomic()`. None of `Prospect.email`, `.website`, or `.raw_payload_hash` (`leads/models.py:58,63,67`) are `unique=True`. Two near-simultaneous promote calls for the same result (double-click, or owner + admin both hitting it) can both pass the check and create two `Prospect` rows.

6. **N+1 query on the non-admin AI search job list.** `dashboard/api/views.py:666-667` queries `AISearchJob.objects.all()` with no `select_related("owner")`, but `AISearchJobSerializer` includes `owner_username` (`source="owner.username"`), firing one extra query per row (up to page_size=100). The admin equivalent (`admin_views.py:847`) already does this correctly — the fix just wasn't applied to the non-admin path.

7. **Stuck-forever `pending` jobs with no recovery path.** `dashboard/api/views.py:646-653` / `admin_views.py:823-830` create the `AISearchJob` row and call `.delay()` with no `try/except` and no transaction. If the Celery broker is briefly unreachable, `.delay()` raises, the view 500s, but the job row is already committed as `pending` and never picked up. There is no periodic sweep in `CELERY_BEAT_SCHEDULE` to requeue stale jobs — only a human noticing and using `rerun_job` (which, per #4, isn't safe if the job is actually still mid-flight).

### Frontend

8. **Field-level validation is dead code.** `AiSearchPage.tsx:39` calls `useForm<AiSearchFormValues>()` with no `resolver` (no `zodResolver`), so `form.formState.errors.seedTopic?.message` (line 362) is always `undefined`. Real validation happens manually in `onSubmit` via `aiSearchFormSchema.safeParse`, but it only sets a page-level banner — never a field-level error. Submitting with an empty seed topic shows a generic top-of-page banner, not an inline error on the actual invalid field.

9. **No error handling for any of the three page queries.** None of `jobsQ`, `detailQ`, `usersQ` (`AiSearchPage.tsx:48-83`) check `.isError` anywhere in the JSX. A failed jobs/detail/users fetch renders as an empty state ("No jobs yet.", "No results for this job yet.", empty owner dropdown) — visually indistinguishable from a legitimately empty result.

10. **Recent-jobs table goes stale during a run.** `jobsQ` has no `refetchInterval` — it only refreshes on job creation and when the *currently selected* job's polled detail transitions to a terminal state. If the user never opens the detail panel for a running job, its row in the list keeps showing a stale status (e.g. "pending") indefinitely.

11. **No client-side throttle on job submission (cost control gap).** The submit button (`AiSearchPage.tsx:381`) only disables for the duration of the POST itself (`createM.isPending`), not while a job is actually running server-side. Combined with backend finding #(rate limiting) below, a user can fire off many jobs back-to-back, each burning real Gemini/Serper budget, with no UI warning.

## 3. Security / cost concerns

12. **Prompt injection via scraped page content.** `crawler/services/ai_page_extract.py:113-134` splices up to 24,000 chars of raw fetched page text directly into the Gemini prompt via f-string; the system prompt has no instruction to disregard directives embedded in that content. Since the model's output directly gates promotion into `Prospect` (translation-need score, competitor/directory flags, extracted contact email), a malicious page author could craft text to force a high score and a fabricated contact email, getting a bogus lead force-promoted into the sales pipeline. The independent rule-based gates in `active_buyer.py` run over the same attacker-controlled text, so they're only a partial mitigation.

13. **No LLM-cost-specific rate limiting.** The only throttle on job creation is a generic `DashboardUserRateThrottle` at 120/min. A single job can trigger on the order of 40+ Gemini calls (query generation + grounded search + up to 12×3 extraction retries). There's no per-user daily/hourly cap on job count or Gemini spend — see also frontend finding #11.

14. **Broad admin trust boundary.** `IsDashboardAdminUser` (`dashboard/api/permissions.py:17-24`) is just `request.user.is_staff` — any staff user can list, view, and promote *any other user's* AI search jobs/results via the `/admin/` endpoints, scoped only by an activity-log entry after the fact, not by ownership.

## 4. Design concerns / tech debt

15. **Misleading error classification.** `extract_prospect_from_page_safe` (`ai_page_extract.py:154-174`) labels *any* terminal failure on the final retry as `quota_exhausted: True` — not just actual 429/`RESOURCE_EXHAUSTED` responses — muddying root-cause diagnosis (quota vs. auth vs. transient network failure all look identical downstream).

16. **`EventProspect.ai_search_result` FK is defined but never populated.** The only code path that creates `EventProspect` rows (`crawler/services/event_processor.py:71-99`) never sets this field — any report trying to trace an event prospect back to its originating AI search job will always find `NULL`.

17. **Email-based dedup in promotion can silently merge unrelated leads.** Treating a shared `contact_email` as proof of "same organization" (`promote_ai_result.py:74-75`) is unsafe against tender/procurement portals that reuse one generic inbox across many distinct buyer organizations — a second, genuinely different result would resolve to the first `Prospect` instead of creating a new one.

18. **Inconsistent domain string formats between directly related models.** `AISearchResult.domain` is a bare hostname; `DiscoveredDomain.domain` (the target of `AISearchResult.queued_domain`) is a full `https://...` URL. Internally consistent per model, but a trap for new code written against both.

19. **No test coverage for the task or API layer.** `crawler/tests.py` covers only pure helper functions; there is no test exercising `run_ai_search_job` itself (retry/timeout/failure paths), and `dashboard/tests.py` has zero AI-search references. None of findings #3–#7 or #12–#14 are covered by any test.

20. **Frontend type gaps papered over with assertions.** `queries_generated` is typed `unknown[]` and cast unchecked at `AiSearchPage.tsx:436`; a `ColumnDef` assertion at line 176 works around a conditional-column type-inference gap. Both are currently safe in practice but not enforced.

21. **Frontend/backend field-limit mismatch.** The backend silently truncates `seed_topic` to 500 chars and `industry`/`region` to 200 chars server-side (`dashboard/api/views.py:644-648`) with no matching `.max()` in the frontend Zod schema and no client-side feedback that truncation happened.

22. **Inconsistent trimming rules across sibling form fields.** `schema.ts` trims `seedTopic` but not `industry`/`region`/`delegateOwnerId`; the mutation manually trims `industry`/`region` before sending, so a whitespace-only value can pass schema validation yet be silently turned into `undefined` in the actual request — schema-valid and actually-sent data can diverge.

23. **Operational debug text leaks to non-admin users.** The "pending worker" hint on the staff-facing page literally instructs the user to run `celery -A leads_app worker -l info` on the server — an ops instruction with no actionability for a staff user, and a sign the empty/pending state text wasn't reviewed per-audience.

24. **No independent client-side timeout backstop.** Detail polling (`AiSearchPage.tsx:73-82`) continues indefinitely for a non-terminal job; the shown copy asserts the worker will fail the job after ~5 minutes, but the frontend has no fallback if that assumption doesn't hold (e.g. the pre-execution stuck-`pending` case in backend finding #7).

25. **Minor accessibility gaps.** Icon-only action buttons rely on `title` rather than `aria-label` (weaker cross-AT support); the shared `FormField` component doesn't wire `aria-describedby`/`aria-invalid` between inputs and their error text (currently moot for this page per #8, but a component-level gap).

26. **Thin test coverage on the frontend schema.** `schema.test.ts` only covers empty/whitespace `seedTopic` rejection and one fully-valid payload — no coverage of `delegateOwnerId`, the trim inconsistency in #22, or overlong-field cases.

## 5. Cross-cutting observations

- The backend's failure handling *within* a running task is solid (both `SoftTimeLimitExceeded` and generic exceptions correctly mark the job `failed` — `crawler/tasks.py:670-690`). The real reliability gap is at the edges: **pre-execution** (broker unavailable at enqueue → orphaned `pending` row, backend #7) and **re-execution** (no idempotency guard, backend #4) — both invisible to the frontend, which just polls and eventually gives up waiting on a job that will never move (frontend #10, #24).
- No model/migration drift was found (`AISearchJob`/`AISearchResult` match migrations 0009–0015 exactly).
- Cost/rate-limiting is a gap on both ends: nothing server-side beyond a generic per-minute request throttle, and nothing client-side beyond disabling the button for the POST's duration (backend #13, frontend #11) — these compound into the same real risk (unbounded LLM spend from repeated submissions).
