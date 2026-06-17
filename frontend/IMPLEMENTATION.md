# Dashboard Rework — Implementation Plan

Phased rollout. Each phase keeps the app shippable; old import paths remain via re-export shims until migration completes.

## Decisions (locked for this rework)

| Topic | Choice |
|-------|--------|
| Staff vs admin shell | **Unified `AppShell`** with separate nav configs |
| API layer | **Hand-split modules** under `shared/api/`; `lib/api/dashboard.ts` re-exports |
| Tables | **TanStack Table** via shared `DataTable` |
| Forms (later) | react-hook-form + zod for Target / AI search |
| Realtime | Keep polling for now; SSE in Phase 5 |
| Route structure | Keep existing URLs; migrate page implementations in place |

---

## Phase 1 — Foundation (current)

**Goal:** Shared infrastructure + prove pattern on pipeline pages.

- [x] `IMPLEMENTATION.md` (this file)
- [x] `shared/api/` split + `getApiErrorMessage`
- [x] `shared/hooks/` — `useDebouncedValue`, `useServerList`, `useRowSelection`
- [x] `shared/components/` — `PageHeader`, `StatusBadge`, `AlertBanner`, `DataTable`, `Input`, `Select`, `ListPagination`
- [x] `shared/layouts/AppShell` — unify staff + admin layouts
- [x] Migrate **Prospects** + **Leads** lists (pagination, debounced search, URL filters)
- [x] Fix login redirect for admin role
- [x] Fix **AdminPipelinePage** (admin-safe content, no staff redirect)

**Exit criteria:** `npm run build` passes; prospects/leads usable with new table UX.

---

## Phase 2 — Scraper domain (current)

- [x] Migrate `TargetsPage`, `TargetFormPage`, `RunsPage`, `RunDetailPage`
- [x] Shared `RunStatusBadge`, scrape run polling (`pollIntervalWhenRunning`)
- [x] URL-synced filters on runs list (`target_id`, `status`)
- [x] Wire target wizard API (`/dashboard/wizard/*`) in React target form

---

## Phase 3 — Crawler domain

- [x] Extract crawler sub-layout (`/crawler/*` nested routes)
- [x] Migrate Discover, Domains, Runs, Run detail
- [x] Slim down `CrawlerHomePage` (hub only — link out to sub-pages)
- [x] Consolidate query keys under `crawler.*` prefix

---

## Phase 4 — Admin consolidation

- [x] Migrate admin section components to `features/admin/`
- [x] Tab layout for scraper/crawler admin (reduce duplicate overview + sub-routes)
- [x] Full admin pipeline table (cross-user prospects/leads)
- [x] Users, audit, settings, monitoring on shared table patterns

---

## Phase 5 — Polish & cleanup

- [x] Staff home dashboard refresh
- [x] AI search page on shared form components
- [x] CSV export buttons
- [x] SSE runs stream OR remove dead client code
- [x] Delete `PlaceholderPage`, update README
- [x] E2E smoke tests

---

## File map (target end state)

```
src/
├── shared/
│   ├── api/
│   ├── components/
│   ├── hooks/
│   └── layouts/
├── features/
│   ├── pipeline/     # Phase 1
│   ├── scraper/      # Phase 2
│   ├── crawler/      # Phase 3
│   └── admin/        # Phase 4
├── app/              # router, providers, nav (unchanged entry)
├── contexts/
└── pages/            # thin re-exports → features/* (during migration)
```

---

## Progress log

| Date | Phase | Notes |
|------|-------|-------|
| 2026-06-17 | 2 | Scraper pages migrated to features/scraper |
| 2026-06-17 | 3 | Crawler pages migrated to features/crawler; nested layout + query keys |
| 2026-06-17 | 4 | Admin pages migrated to features/admin; nested scraper/crawler layouts |
| 2026-06-17 | 5 | Home refresh, AI search forms, SSE hook, vitest smoke tests, README |
