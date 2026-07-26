# Discovery Quality Analysis — Why Web Crawler & AI Search Results Miss the Mark

*Generated 2026-07-26. Follow-up to `CRAWLER_ANALYSIS.md` / `AI_SEARCH_ANALYSIS.md` (2026-07-19) — those covered correctness bugs (crash/race/security), most since fixed. This document covers a different question: **why do the results these two pipelines surface not match what a Language Service Provider (LSP) actually wants to find** — organizations that need translation, interpretation, localization, sign-language interpreting, rapporteuring, or conference-equipment services.*

---

## 1. Executive summary

Both pipelines' scoring logic **is** genuinely LSP-aware — the keyword lists, org-type detection, and Gemini prompts are explicitly written around "who buys translation/interpretation services," not generic lead-gen. That part is not the problem.

The problem is a **shared filter chain that runs before scoring ever happens**, plus **one specific cross-pipeline bug that lets a second, weaker scoring system silently create duplicate low-quality prospects behind your back**. Concretely:

1. **`is_org_homepage_or_careers_hub` unconditionally rejects any search result that lands on a domain's root URL** (`path in ("/", "")`) — before anything about the page's content, translation-relevance, or org type is even checked. Since a normal Google/Serper search for "NGO language services Africa" or "international conference East Africa" overwhelmingly returns organization homepages, **this one check is very likely discarding the majority of exactly the kind of lead you want**, before scoring ever runs.
2. **Both Discover (manual) and AI Search require an *active, dated* tender/RFP/hiring signal on the page** (`CRAWLER_REQUIRE_ACTIVE_BUYER` / `AI_SEARCH_REQUIRE_ACTIVE_BUYER`, both on by default). That's a valid, narrow strategy ("find live procurement opportunities right now") but a very different, much smaller target than "find organizations that generally need our services" — which is what a normal international NGO/university/hospital/law-firm/conference-organizer homepage would signal, with no live tender posted today. If what you actually want is broader prospecting, this gate is the single biggest reason results are thin.
3. **A hard East Africa geo gate is on by default**, silently rewriting every query and rejecting any page that doesn't mention the region. (This may be *intentional* — Ateric appears to be East-Africa-based — but it's worth an explicit yes/no rather than an inherited default.)
4. **A confirmed cross-pipeline bug**: every domain AI Search discovers also gets queued into the general crawler's shared domain pool. Up to 12 hours later, the *scheduled* crawler independently re-scores that same domain with a **different, weaker, non-buyer-aware Gemini rubric**, and if it scores above a much lower bar (`> 40` vs. AI Search's 80), it **auto-creates a second Prospect** — owned by nobody (`owner=None`), labeled `source_name="web_crawler"` instead of `"ai_search"`, and **stripped of the evidence** (`evidence_snippet`, `why_needs_translation`, `buyer_signal_type`) that made the original AI Search hit credible. This is likely a real, visible source of "the tool surfaces things that don't look like what I asked for."
5. Smaller but real: AI Search's own query generation is mostly hardcoded templates (Gemini's actual output is heavily overwritten); a Kenya-only `site:.go.ke` clause is hardcoded regardless of selected region; a per-job Gemini budget silently leaves up to 23 of 35 candidates unscored (and unpromotable, with no visible reason why); three different, inconsistent "low/medium/high" vs. "hot/warm/cold" labeling schemes exist in parallel; and some genuinely useful code (`PRIORITY_PATHS` for crawl prioritization, LLM-derived `prospect_signals` for per-query tuning) is written but never wired up.

**Bottom line**: the scoring "brain" is fine; the qualification "gates" in front of it are tuned for a narrower job (live East-Africa procurement hunting) than the tool's stated purpose (LSP prospecting in general), and a real bug lets a second, worse gate quietly override the first one's good work.

---

## 2. How each pipeline works today (brief — see the two audits above for full code walkthroughs)

### Web Crawler (Discover page + scheduled `CrawlSource` discovery)
`Discover` (search phrase you type, or a scheduled `CrawlSource` query) → Serper/Bing search → **`discovery_qualify.py` filter chain** (stale-URL check → live page fetch → homepage/careers-hub rejection → geo gate → directory/aggregator check → competitor check → active-buyer gate) → surviving hits become `DiscoveredDomain` rows → scheduled `crawl_domain_task` does a robots-respecting BFS crawl (≤25 pages, depth 2) → `analyze_domain_task` scores the crawled text (keyword rules, or Gemini if configured — Gemini wins when both are available) → `score_and_create_prospect_task` auto-creates a `Prospect` if score `> 40` (`CRAWLER_MIN_SCORE_THRESHOLD`).

### AI Search (`/find-leads`)
Seed topic + industry + region → Gemini-assisted query generation (heavily supplemented by hardcoded templates) → Serper company-first search (or Gemini-grounded search as fallback) → up to 35 candidates → one page fetch each → **the same `discovery_qualify`-style gates** (homepage rejection, geo, directory, active-buyer) plus a dedicated Gemini page-scoring prompt (binary-ish 0-39 reject / 80-100 accept, budget-capped at 12 calls/job) → surviving results become `AISearchResult` rows, and **independently** get queued into the same `DiscoveredDomain` pool the crawler uses → user reviews and manually promotes to `Prospect`.

The overlap in the last step of AI Search is where finding #4 above comes from.

---

## 3. Detailed findings

Ordered roughly by expected impact on "why don't results match what I want."

### F1 — Homepage/root-URL rejection discards most organic leads (Critical)
**Where**: `crawler/services/active_buyer.py::is_org_homepage_or_careers_hub`, called unconditionally from `discovery_qualify.py::filter_discovery_hit` (Discover) and `ai_page_extract.py::qualify_ai_search_candidate` (AI Search) via `preflight_candidate_page`.
**What happens**: `if path in ("/", ""): return True` — any search hit whose URL is just the domain root is instantly classified as a "generic hub page" and dropped, with zero regard for what's actually on that page.
**Why it matters**: search engines return domain roots constantly for organizational queries ("NGO language services Africa," "international association annual meeting" — both are the frontend's own example queries). A great prospect — an NGO, university, or hospital whose homepage plainly describes international, multilingual operations — is discarded here before translation-relevance is ever evaluated.

### F2 — "Active buyer" requirement narrows the target to live procurement, not general fit (Critical, philosophy-dependent)
**Where**: `CRAWLER_REQUIRE_ACTIVE_BUYER` (default on) and `AI_SEARCH_REQUIRE_ACTIVE_BUYER` (default on); enforced via `active_buyer.py::passes_active_buyer_gate` / `check_forward_timeline`; the AI Search scoring prompt is explicitly instructed *"Do NOT use [40-79] — score below 40 unless 80+ criteria met,"* i.e. score is effectively binary: "live tender/RFP/hiring notice with a future date" (80-100) or "reject" (0-39). An org that's clearly an international NGO/law firm/hospital/conference organizer, with no dated tender posted today, scores near 0.
**Why it matters**: this is a valid, narrow strategy if the goal is "find live bids to respond to right now." It's the wrong strategy if the goal is "build a prospect list of organizations that plausibly need our services" (the more typical LSP business-development motion, and the setup this tool otherwise reads as built for — see decision **D1** below).

### F3 — East Africa geo gate is hardcoded on by default (High, needs confirmation not necessarily a bug)
**Where**: `CRAWLER_GEO_MODE=east_africa` (default), `crawler/services/geo_filter.py`. Silently prepends `"Kenya Uganda Tanzania Rwanda Burundi South Sudan Ethiopia East Africa EAC"` to every Discover query, biases Serper's own `gl`/`location` params to Kenya, and rejects any page not mentioning an East Africa term or country-code TLD.
**Why it matters**: if East Africa genuinely is the target market (plausible — Ateric appears East-Africa-based), this is correct and should stay. If the business also wants leads from Europe/elsewhere (the UI's own example query is literally "translation conference **Europe**"), this gate silently defeats that query. **This needs an explicit answer from you (see D2), not a code guess.**

### F4 — Cross-pipeline duplicate/downgrade bug (Critical — confirmed bug, not philosophy)
**Where**: `crawler/tasks.py::run_ai_search_job` unconditionally upserts every AI-Search-discovered domain into the shared `DiscoveredDomain` table (`priority=8`, `crawl_status="pending"`). The independently-scheduled `discover_websites_task` (Celery beat, every 12h by default) later picks up that same domain, crawls it, and scores it via `gemini_analyzer.py`'s **generic** rubric (no active-buyer awareness, no date-freshness check, no directory check, graded 0-100 with an "international operations" framing rather than "active buyer"). If `profile.gemini_translation_need_score` is set, `score_and_create_prospect_task` uses it **instead of** re-deriving anything from the original AI Search evidence, and auto-creates a `Prospect` the moment the score exceeds just `40`.
**Consequences**:
- A second `Prospect` for the same organization can appear, credited to `source_name="web_crawler"` instead of `"ai_search"` — its true origin is invisible.
- It's created with `owner=None` (the scheduled task has no acting user), a **different ownership scope** from the one you'd get by manually promoting the AI Search result — so it doesn't dedupe against your careful review, it just shows up as a second, unexplained row.
- Its `raw_payload` carries none of the original evidence (`evidence_snippet`, `why_needs_translation`, `buyer_signal_type`) — exactly the context that made the AI Search hit credible in the first place is gone.
- It can fire off a stale opportunity: a tender that was live and evidence-backed when AI Search found it can be long closed by the time the scheduled re-crawl happens weeks later, but the generic scorer never checks dates at all.

This is very plausibly a direct, visible cause of "the tool surfaces things that don't look like what I asked for" — some fraction of what lands in the Review queue may be these generic, unexplained duplicates riding in on domains AI Search touched.

### F5 — Query generation is mostly hardcoded, not really "AI search" (Medium)
**Where**: `crawler/services/ai_search.py::_boost_queries_for_lsp`. Gemini's generated queries get merged with, and largely overwritten by, `company_first_query_templates` (8 fixed templates) plus up to 3 more injected fallback templates plus 3 more appended generic ones — and any surviving Gemini query lacking a "buyer intent" keyword gets a literal string suffix bolted on. Most of the actual search strings sent to Serper come from fixed templates with the seed topic spliced in, not from what Gemini generated for *this specific* seed topic.
**Why it matters**: less flexible than it appears — a seed topic that doesn't fit the hardcoded template shapes well (e.g. a specific named event, or a niche industry) gets steamrolled by generic templates rather than a tailored query.

### F6 — `site:.go.ke` hardcoded to Kenya regardless of selected region (Low-Medium)
**Where**: `crawler/services/company_discovery.py` — one of the 8 templates is hardcoded to Kenya government domains specifically, while every sibling template correctly uses the resolved `{geo}` region string.
**Why it matters**: if a search targets Uganda/Tanzania/Rwanda government tenders specifically, this template silently only ever searches `.go.ke`.

### F7 — Gemini extraction budget silently leaves candidates unscored and unpromotable (Medium)
**Where**: `AI_SEARCH_MAX_GEMINI_EXTRACTS` (default 12) caps page-scoring calls per job, but up to 35 candidates can reach that step. Once exhausted, remaining candidates fall through to rules-only qualification and can still be written to `AISearchResult` with `translation_need_score=None`. `result_promotable()` treats `None` as not-promotable.
**Why it matters**: these rows appear in your results list looking like normal candidates, but "Promote" always silently rejects them — with no visible score or reason shown, so it looks broken rather than budget-limited.

### F8 — Two independent LLM scoring rubrics, three label vocabularies (Medium)
- AI Search's page scorer (binary-ish, active-buyer framing) vs. the general crawler's domain scorer (graded, "looks international" framing) — different questions, different scales, feeding the same `translation_need_score` field name.
- `crawler/scoring.py::get_score_label` (low/medium/high, ≤30/≤60/>60) vs. `gemini_analyzer.py::score_label` (cold/lukewarm/warm/hot, <40/<60/<80/≥80) vs. `gemini_label_to_bucket` (maps the second onto the first's vocabulary with yet other boundaries) — the latter two are **dead code**, never called anywhere, but their existence makes the scoring story harder to reason about and easy to reintroduce inconsistently.

### F9 — Dead/half-finished code worth knowing about (Low, but easy wins)
- `crawler/constants.py::PRIORITY_PATHS` (a curated list of high-signal paths like `/events`, `/programmes`, `/about`) is defined but **never referenced** — the crawl's BFS has no path prioritization, so within a 25-page/depth-2 budget, high-signal pages may never be reached on a larger site while low-signal ones are.
- `derive_competitor_signals()` computes per-query, Gemini-derived `prospect_org_types`/`prospect_signals` ("what does a good prospect look like for *this* query") but the signal receiver only ever persists `competitor_keywords`/`competitor_org_types` — the "what makes a good prospect" half of that feature is silently discarded every time.
- `CrawlSource` seed queries (10 hardcoded queries from an early migration) have the year 2026 baked into their text — they'll need manual refreshing or they'll keep searching a fixed year.
- `CRAWLER_MIN_SCORE_THRESHOLD` compares with strict `>`, not `>=` — a domain scoring exactly 40 (labeled "medium" everywhere else) is never promoted. Minor, but confusing when auditing why a "medium" domain never became a Prospect.
- `AI_SEARCH_MAX_CONCURRENT_JOBS_PER_USER` is referenced in code but never declared in `settings.py`/`.env.example` — works (defaults to 1), just undocumented.
- No per-search UI control for `strict_active_buyer` or geo mode — they're global env vars, so every single search gets the same defaults regardless of what kind of query you're running that day.

---

## 4. Decisions (finalized 2026-07-26)

**D1 — (c) Both modes.** Default to broader prospecting (any org that plausibly needs our services), with an "active opportunities only" filter/toggle for when live tenders/RFPs are specifically wanted. Also: **widen beyond NGOs** — target a genuinely wide variety of industries (corporate, legal, healthcare, academic, financial, government, diplomatic, manufacturing/trade, media, hospitality/events, religious/faith organizations, sports federations, etc.) that plausibly buy translation/interpretation/localization, not just the NGO/international-development framing the current query templates and prompts lean on.

**D2 — Geo scope is service-delivery-mode-dependent, not a single global toggle.** This is more nuanced than a single east_africa/global switch:
- **Physical-presence services** — simultaneous interpretation, conference interpretation, liaison/interactive interpretation, sight translation, and any engagement requiring interpretation equipment or an on-site interpreter — **stay East-Africa-scoped, with Kenya as the priority market.** These require the org (or its event) to physically be in-region, so a hit anywhere else is not a usable lead for these specific services.
- **Location-agnostic (virtual/deliverable) services** — virtual interpretation, virtual conference interpretation, document translation, localization, rapporteuring — **search both global and East Africa.** These don't require physical presence, so geography shouldn't gate them out.
- Net effect: the geo gate must become **conditional on which service the candidate appears to need**, not a single global env var applied uniformly to every search. See §5 Phase 4 for the mechanism.

**D3 — (b).** The general crawler keeps re-visiting AI-Search-discovered domains (crawl data refresh has value), but it must never auto-create a *second* Prospect for a domain that already has a linked `AISearchResult`/Prospect — ownership/dedup scoping needs to actually catch this, and the weaker generic rubric must not be able to override or duplicate an AI-Search-sourced Prospect.

---

## 5. Proposed implementation plan (phased, for your review — no code changes yet)

### Phase 0 — Your decisions (D1/D2/D3 above)
Blocks everything below; the fixes differ materially depending on the answers.

### Phase 1 — Fix the confirmed cross-pipeline bug (F4)
No philosophy dependency; this is close to a straight bug fix regardless of D1/D3's exact answer.
1. Stop auto-creating a `Prospect` from the general crawler pipeline for any `DiscoveredDomain` that already has a linked `AISearchResult` (or, per D3(a), stop queuing AI-Search domains into the shared pool at all).
2. If a Prospect already exists for that domain (however it arrived), never silently create a second one — this should already be true via the dedup logic in `prospect_pipeline.py`, but the `owner=None` vs. real-owner scoping gap means it currently isn't; align ownership/dedup scoping so a scheduled-run Prospect can actually match one a real user already has.
3. Add a regression test: an AI-Search-discovered domain that later gets independently crawled must not produce a duplicate/lower-quality Prospect.

### Phase 2 — Relax the over-broad rejection gate (F1)
1. Replace the unconditional "root URL = generic hub, reject" rule with an actual content check — a homepage should only be rejected if its *content* doesn't show LSP-relevant signals (org type, services, international/multilingual indicators), not merely because of its URL shape.
2. This one change should measurably increase both pipelines' hit rate without touching the active-buyer/geo logic at all — worth shipping and testing in isolation before Phase 3.

### Phase 3 — Implement D1 (both modes, wide industry range)
1. Add a "general prospect" qualification path alongside the existing "active buyer" path — same scoring, but the promotion gate no longer requires a dated tender/RFP/hiring signal, just a sufficiently strong LSP-relevance score (org type + service signals + international indicators). Default to this path; the active-buyer path becomes an opt-in filter.
2. Expose the choice per-search on the Discover and Find-new-leads pages (a toggle: "Any organization that might need us" vs. "Only active tenders/RFPs right now").
3. Re-tune the AI Search scoring prompt so "general prospect" mode uses the full 0-100 scale (today's prompt explicitly forbids the 40-79 band) — a graded scale is what lets "Strong match / Possible match" language mean something in this mode.
4. Broaden the org-type/industry framing everywhere it's currently NGO/international-development-leaning: `_LSP_SERVICE_CONTEXT` and `generate_search_queries`'s prompt in `ai_search.py`, `company_first_query_templates` in `company_discovery.py`, and `ORG_TYPE_KEYWORDS` in `analyzer.py` — add categories/templates for corporate, legal, healthcare, academic, financial, government, diplomatic, manufacturing/trade, media, hospitality/events, faith-based, and sports-federation organizations, not just NGOs/conferences.

### Phase 4 — Service-mode-aware geo gating (D2)
This replaces the single global `CRAWLER_GEO_MODE` switch with logic that depends on *which service* the candidate looks like it needs:
1. Define two service groups (reusing/extending `SERVICE_KEYWORDS` in `analyzer.py`): **physical-presence** (simultaneous interpretation, conference interpretation, liaison/interactive interpretation, sight translation, interpretation-equipment/booth/on-site language) vs. **location-agnostic** (virtual interpretation, virtual conference interpretation, document translation, localization, rapporteuring, transcription/subtitling).
2. Add a per-search **service scope** control (Discover, Find-new-leads, and `CrawlSource` config): "Physical-presence services (Kenya / East Africa only)," "Virtual/deliverable services (global + East Africa)," or "Auto-detect from query/content." Auto-detect classifies the seed topic or discovery query text against the two keyword groups to pick a mode when the user doesn't specify one.
3. Wire the geo gate (`geo_filter.py`) to branch on this: physical-presence scope keeps today's strict East-Africa/Kenya-priority gate; location-agnostic scope disables the hard geo rejection (global + East Africa both pass) while still using region as a *ranking* signal, not a hard filter.
4. At the content-scoring stage, cross-check: if a candidate was found under location-agnostic scope but the page's actual service signals are physical-presence-only (e.g. it's specifically advertising an on-site conference), and the org is outside East Africa, flag it as lower-confidence/non-actionable-by-us rather than silently promoting it — the physical constraint is real regardless of which scope found the lead.
5. Fix F6 (`site:.go.ke` hardcode) as part of this — it only makes sense for the physical-presence Kenya-priority path, not for every region.

### Phase 5 — Consistency & cleanup (F5, F7, F8, F9)
1. Fix `site:.go.ke` to use the resolved region's actual government-domain pattern (or drop the template if not generalizable).
2. Surface "not yet scored (rate-limit reached)" as a distinct, visible state in the AI Search results UI instead of a silently-unpromotable `None` score.
3. Delete the dead `gemini_analyzer.py::score_label`/`gemini_label_to_bucket` functions; standardize on the one label vocabulary (`crawler/scoring.py::get_score_label`) everywhere a label is shown.
4. Wire `PRIORITY_PATHS` into the BFS crawl's URL-queue ordering so high-signal pages are more likely to be reached within the page/depth budget.
5. Either persist `prospect_org_types`/`prospect_signals` from `derive_competitor_signals()` and use them to tune per-query scoring, or remove that half of the computation if it's not worth finishing.
6. Add a small admin/scheduled job (or at least a documented manual step) to refresh the year-hardcoded `CrawlSource` seed queries.
7. Fix the `CRAWLER_MIN_SCORE_THRESHOLD` strict-`>`/label-boundary mismatch (either change to `>=` or move the threshold to a value not exactly on a label boundary).
8. Document `AI_SEARCH_MAX_CONCURRENT_JOBS_PER_USER` in `settings.py`/`.env.example` instead of leaving it as an undocumented fallback.

### Verification, every phase
Build + existing test suite + a live before/after comparison: run the same 3-4 seed topics/search phrases through both pipelines before and after each phase and compare result counts/quality, since "does this feel right" is ultimately a judgment call only you can make on real output, not something a test suite alone can certify.

---

## 6. Explicitly out of scope for this plan (unless you say otherwise)
- Rewriting the crawl engine itself (BFS strategy, Playwright fallback, rate limiting) — those are working as designed; only *which* pages get prioritized (F9) is in scope.
- Changing which LLM/provider is used (Gemini, Serper/Bing) — this is about gate logic and scoring rubric, not vendor choice.
- The admin portal's parallel views over the same data — out of scope per the same boundary used for the earlier UI redesign work.
