# Frontend UI Analysis & Redesign Plan for Non-Technical Users

*2026-07-20 — analysis based on reading every staff-facing page component AND running the live app (Django + Vite) and walking the real screens as a fresh staff user. This is a plan for review — no code has been changed.*

**Supervisor feedback being addressed:** the UI has too much text and too many card sections, and is not easy for non-technical users.

**Verdict up front:** the feedback is accurate, and the root cause is deeper than styling. The UI is organized around *how the machine works* (scraper → crawler → domain queue → runs → pipeline) instead of *what the user is trying to do* (find potential customers, review them, contact them, track the interested ones). The text-heaviness and card-soup are symptoms: every screen tries to *explain the machinery* because the machinery is what's on screen. Rename and restyle alone won't fix that — but a staged plan can get visible improvement quickly and restructure safely.

---

## 1. Who this is for (working persona)

A staff member whose job is **lead review and outreach**: look at newly discovered organizations/events, decide which are worth contacting, mark progress, and keep the interested ones moving. They do not know (or need to know) what a CSS selector, domain queue, SERP, or Celery run is. The admin/ops persona (configuring targets, monitoring runs) still exists but is a different person — or the same person in a rare "setup" moment, not their daily loop.

**The daily loop the UI should optimize:**
1. "Anything new for me today?" → 2. Review each new prospect (who are they, why flagged, when is their event/tender) → 3. Contact / reject / convert → 4. Track interested leads → 5. (Occasionally) ask the system to find more.

Everything else — targets, runs, domains, sources, scoring thresholds — is machinery that supports this loop and should be out of the daily path.

---

## 2. What the screens show today (evidence)

### 2.1 Login
- Title: **"Scraper portal"**, subtitle "Sign in with your staff or admin portal account." A non-technical user's first word from the product is developer vocabulary. (`LoginPage.tsx`)

### 2.2 Staff dashboard (`/`) — the worst offender, and the page the supervisor most likely reacted to
Observed live: **two competing titles** ("Scraper dashboard" in the app-shell header + "Operations dashboard" as the page title), then this description: *"Daily workflows for Scraper, Crawler, and Pipeline. Scraper runs are per-target; crawler uses the domain queue."* — pure internals-speak as the welcome message.

Then, stacked (5 distinct card sections, up to 3 levels of nesting):
1. **4 KPI cards** — "Enabled targets", "Scrape runs (7d)", "Crawl runs (7d)", "New prospects". Three of four are machine metrics; only one relates to the user's job.
2. **Attention banner** (conditional).
3. **"Workflow shortcuts" card containing 4 nested cards** — including a **"Session" card that says "Signed in as staff."** (a debug statement presented as a workflow), and three cards that are just link lists (Targets/Runs, Discover/Overview, Prospects/Leads) duplicating the sidebar.
4. **"Pipeline snapshot"** — 4 more gray number tiles.
5. **"Status distribution"** — a bar chart whose x-axis labels are literally `P:new`, `L:contacted` (code prefixes).
- Header also shows **"Runs updates: live stream"** — an SSE/polling transport indicator no end user can act on. (`StaffHomePage.tsx:64`, `213-227`)
- A fresh user sees **all zeros and an empty chart with zero guidance** on what to do first.

### 2.3 Prospects (`/prospects`) — the most important page, closest to good
The table itself is decent (Company, Event, Event date, Email, Status). Problems observed live:
- **Four buttons on every row** (View, Contacted, Convert, Reject — two of them red/filled), so a 5-row table renders **20 buttons**; the action noise outweighs the data. (`ProspectsPage.tsx:147+`)
- Three more bulk buttons + Export CSV live in the header, styled at similar weight.
- "Convert to leads" is internal vocabulary — users think "this one is worth pursuing", not "convert".
- Subtitle again explains machinery: "Review crawler discoveries and move qualified contacts into the lead pipeline."
- **Sidebar footer shows `API: {proxy → :8000}`** — a developer debug line visible to every user on every page. (`Sidebar`/`AppShell` area)
- No "why was this found?" context on the row — the one thing a reviewer actually needs (score/evidence exist in the data but aren't surfaced).

### 2.4 New target (`/targets/new`)
"Use **smart setup to auto-detect selectors**, or switch to **manual JSON configuration**" / "…we detect Eventbrite, Meetup, and other platforms and **pre-fill CSS selectors**." Tabs: "Smart setup" / "Manual JSON". The wizard idea is right; the copy is for developers. (`TargetFormPage.tsx`, `TargetWizardPanel.tsx`)

### 2.5 Crawler overview (`/crawler`) + sub-tabs (Discover, Domains, Runs, AI search)
Description: *"Discovery sources feed the domain queue; runs track batch progress. Separate from scraper targets and scrape runs."* — explaining an internal distinction (scraper vs crawler) that **should not exist for the user at all**. A numbered "Crawler workflow" card with 4 nested step-cards ("Ad-hoc search", "Sources", "Domain queue", "Runs & results"), then 4 more stat cards ("Pending domains", "Crawling now"…). Buttons: "Run scheduled discovery", "Cancel all running". This entire section is an ops console. (`CrawlerHomePage.tsx`)

### 2.6 AI search (`/crawler/ai-search`)
Description names our vendors and internals to end users: *"Company-first **Serper** discovery plus **Gemini** page scoring. Only lead-worthy hits (**score ≥ 60**) are saved; promote them directly to your pipeline."* Label "Seed topic". Results grouped as "Recent **jobs**". Functionally this is the most non-tech-friendly capability in the product ("describe what you want, get leads") — buried under Crawler with the most technical copy in the app. (`AiSearchPage.tsx`)

### 2.7 Scrape runs (`/runs`)
"Trigger selected target", run IDs, Items/Leads counts. Purely an ops view; fine for admins, meaningless for staff.

### 2.8 Cross-cutting
- **Terminology**: scrape/scraper (nav, titles, login), crawler, targets, runs, domain queue, sources, seed topic, jobs, convert, promote, SERP-ish phrases — everywhere.
- **Duplication**: sidebar sections ↔ home "Workflow shortcuts" ↔ crawler "workflow" cards all present the same links; three surfaces to maintain, three chances to confuse.
- **Visual weight**: the primary red is applied to many competing buttons per screen (Prospects rows have 2 red buttons per row); red also reads as "destructive/error" to most users, so the calm path looks alarming.
- **Two-title pattern** on every page (static shell header + page header).
- **What already works well** (keep): clean shadcn/Tailwind base, sensible tables with pagination and debounced search, status badges, dark mode, mobile drawer, the loading/error states we added, the wizard concept, and the underlying feature set — nothing here needs a rebuild, it needs re-packaging.

---

## 3. Design direction (the one big idea)

**Reorganize the app around the user's job; move the machinery behind an "Advanced" curtain.**

Proposed staff information architecture (sidebar):

| Today (7 items, 4 groups) | Proposed (5 items, plain language) |
|---|---|
| Dashboard | **Home** — "what needs my attention today" |
| Targets / Scrape runs (Scraper) | **Find new leads** — one page: describe what you want (AI search as the hero), see discoveries arrive |
| Crawler (5 sub-tabs) | **Review** — the prospect review queue (today's Prospects) |
| Prospects / Leads (Pipeline) | **My leads** — tracked/interested leads (today's Leads) |
| — | **Automation** *(collapsed/advanced)* — targets, runs, crawler sources/domains, for the rare setup moment; unchanged pages inside |

Key moves:
1. **Merge "Scraper vs Crawler vs AI search" into one concept: "finding leads."** Users pick *what* they want found; which engine does it is an implementation detail. AI search (topic → results) becomes the front door because it's the only discovery flow a non-tech user can operate unaided.
2. **Make Review the center of gravity.** Home's hero is "N new prospects to review" with one button. The review surface leads with *why this was found* (event, date, evidence snippet, score as "Strong match / Possible match") and offers **one primary action per row** ("Review" → detail), with contact/reject/convert in the detail view or a row overflow menu.
3. **Plain-language everything** (full copy table in Phase 1 below).
4. **One title per page, one primary button per screen, cards only when grouping unlike content** — flatten every nested card grid into simple sections or lists.
5. **Status in sentences, not counters.** "Last check: this morning — 3 new prospects found" beats four zero-tiles and a chart. Keep the chart on the admin side.

The admin portal (`/admin/*`) keeps its current technical depth — admins are the right audience for domains/runs/sources — with only the Phase-1 copy/consistency cleanups applied.

---

## 4. Phased implementation plan (for your review)

### Phase 1 — Plain language & de-cluttering (1–2 sessions, low risk, no structural change)
Pure copy/style edits; no routing, API, or behavior changes. Biggest perceived improvement per effort.

1. **Terminology pass** (single sweep across staff pages + login + nav):
   | Current | Replace with |
   |---|---|
   | Scraper portal / Scraper dashboard | Ateric Leads (product name only, once) |
   | Operations dashboard | Home |
   | Prospects → (keep) | "Review queue" as page title, "prospects" ok in body |
   | Convert to lead | Move to My Leads / "Track as lead" |
   | Targets / Scrape runs | Automation → "Sources we check" / "Collection history" |
   | Seed topic | What are you looking for? |
   | Jobs (AI search) | Searches |
   | Trigger / Run scheduled discovery | Check now / Find new leads now |
   | Serper/Gemini/score ≥ 60 copy | "Describe the kind of organization you want; we search the web and keep only strong matches." |
2. **Delete debug/ops artifacts from staff UI**: the "Session" card, `API: {proxy → :8000}` sidebar line, "Runs updates: live stream/polling" indicator, `P:`/`L:` chart prefixes.
3. **One title per page**: shell header shows product name only; pages keep their own H1. Trim every page description to ≤ 1 short sentence or remove.
4. **Calm the buttons**: one filled-primary action per screen; row actions become **View + overflow menu (⋯)** on Prospects/Leads; bulk bar appears only when rows are selected. Reserve red for destructive actions only (introduce a neutral primary color — this is the one visual-theme decision needing your sign-off, see Open Questions).
5. **Empty states that onboard**: each list's empty state says what the page is for and offers the one next step ("No prospects yet — run your first search →").

*Files: `navigation.ts`, `AppShell.tsx`/sidebar, `LoginPage.tsx`, `StaffHomePage.tsx`, `ProspectsPage.tsx`, `LeadsPage.tsx`, `TargetsPage.tsx`, `RunsPage.tsx`, `CrawlerHomePage.tsx`, `AiSearchPage.tsx`, `DataTable.tsx` empty-state prop, button variants. Verification: build + existing tests + screenshot walkthrough.*

### Phase 2 — Home page rebuilt as "what should I do now" (1 session)
Replace the 5-section stack with:
1. **Hero**: "You have **N** new prospects to review" + one button (or "All caught up" + "Find more leads").
2. **Attention strip** (kept, reworded to actions: "3 searches failed — view details").
3. **Recent activity feed** in sentences: "This morning's check of *Eventbrite Nairobi* found 3 new prospects." (data already available from runs/metrics endpoints; formatting layer only).
4. Everything else (KPI grid, shortcuts, snapshot, chart) is deleted or moved to the admin home.

### Phase 3 — Navigation restructure + unified "Find new leads" (1–2 sessions)
1. New sidebar per the IA table above; `Automation` group collapsed by default.
2. New **Find new leads** page: AI search form as the hero (relabeled per Phase 1), a simple "Recent searches" list underneath, and a quiet "Advanced discovery" link to the old crawler Discover/scraper pages for power users.
3. Old routes stay working (redirects), so bookmarks and the admin portal are untouched. Router smoke tests extended.

### Phase 4 — Review flow polish (1–2 sessions, highest UX payoff, needs your input on scope)
1. **Prospect detail as a review card**: who/what/when, the *evidence* ("found on eac.int — tender for interpretation services, deadline Sep 14"), score shown as "Strong match", and three big actions: Contacted / Not relevant / Track as lead.
2. Optional **one-by-one review mode** ("Review 12 new" → card, decide, next) — the most non-tech-friendly pattern possible; a checkbox-table stays available for bulk users.
3. Human-readable run summaries reused anywhere runs appear ("Checked 4 sources, found 6 new prospects, 1 source failed").

**Explicitly out of scope** (unless you say otherwise): backend/API changes (all of this is presentation-layer), the admin portal beyond Phase-1 copy fixes, and any change to how discovery actually works.

---

## 5. Decisions (answered 2026-07-20)

1. **Staff keep crawler & scraper pages** — they scrape sites they find and run crawls themselves. The nav therefore keeps *Find new leads (AI)*, *Web crawler*, and *Site checks* (scraper) as first-class staff items — reworded, not hidden.
2. **Brand palette confirmed from the client logo: `#012269` (navy) + `#e31836` (red)**, white/light background retained. Navy = primary actions/brand; red reserved for alerts & destructive actions (as recommended). Chart palettes derived from these and **validated for color-blind safety** (light: `#2a52b0`/`#0f9e8e`/`#c05f10`; dark: `#4a72d8`/`#159a86`/`#cf6f1d`).
3. **Keep the Prospects / Leads CRM split** — both words stay.
4. **One-by-one review mode: wanted** — included in Phase 4 and demonstrated in the mock.
5. **New requirement — source provenance**: every prospect/domain shows *which feature found it* (AI search / web crawler / site check), with per-source filtering, instead of one undifferentiated domain pool.
6. **New requirement — motion & data visualization**: purposeful animation (count-ups, staggered entrances, review-card transitions; `prefers-reduced-motion` respected) and proper charts (weekly discoveries by source, pipeline stats with sparklines).

A clickable mock of the new Home + Review pages implementing all of the above: `mockups/ui-redesign-mock.html` (also published as a private artifact for supervisor review).

## 6. Remaining open questions before implementation

All five original questions are now answered (see section 5). What remains is sign-off on the mock itself: once you and your supervisor approve (or annotate) the mock, Phase 1 implementation starts against it.

---

*Review notes: test logins `uitest_staff` / `uitest_admin` (password `uitest-pass-12345`) exist in the local dev DB if you want to click through the current UI while reading this. Dev servers: `django` + `vite` configs in `.claude/launch.json`; note `frontend/.env.local` now pins the Vite proxy to plain HTTP for local runs (gitignored). Demo rows created during analysis were removed.*
