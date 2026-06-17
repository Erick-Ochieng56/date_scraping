# Ateric — React dashboard (staff + admin)

React + Vite + Tailwind (shadcn Nova) + TanStack Query + TanStack Table. This SPA is the **staff** operator UI at `/` and the **admin** portal at `/admin`. Legacy Django HTML dashboards may still exist on the backend, but day-to-day operations use this app.

API calls use **`/dashboard/api/*`** (proxied in dev to Django — see `vite.config.ts`).

## Architecture

```
src/
├── app/           # router, lazy pages, nav
├── features/      # domain pages (pipeline, scraper, crawler, admin, home, ai-search)
├── shared/        # api, components, hooks, layouts
└── pages/         # thin re-exports during migration
```

See `IMPLEMENTATION.md` for the phased rework history and `rework.md` for the full audit.

## Dev

1. Start Django from `backend/` (port **8000**), e.g. `python manage.py runserver`.
2. `npm install` then `npm run dev` (Vite **5173**).
3. For HTTPS Django (`runserver_plus`), set `VITE_DJANGO_PROXY_TARGET=https://127.0.0.1:8000` in `frontend/.env`.
4. **Staff:** `http://localhost:5173/login` — users created via `create_staff_user`.
5. **Admin:** same login; users with admin role land on `/admin`.

### RBAC

- **Admin:** `python manage.py createsuperuser` (or grant admin role in the SPA Users page).
- **Staff:** `python manage.py create_staff_user` — portal group, no Django admin access.

```bash
cd backend && python manage.py create_staff_user
```

### Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server with `/dashboard` proxy |
| `npm run build` | Typecheck + production build |
| `npm run test` | Vitest smoke/unit tests |
| `npm run lint` | ESLint |

### Realtime

Scrape/crawl run lists poll automatically while jobs are running. The staff home page also subscribes to **`/dashboard/api/v1/stream/runs/`** (SSE) and invalidates run/metrics queries when events arrive; if the stream is unavailable, polling continues.

### Troubleshooting

**403 on `/dashboard/api/*` via ngrok:** Usually a missing session or a user without portal access (not in the `scraper` group and not `is_staff`). Use a staff account from `create_staff_user`, and log in on the **same origin** as the API.

**Recommended (single ngrok tunnel):**

1. `npm run build` in `frontend/`
2. In `backend/.env`:
   ```
   DJANGO_DEBUG=1
   DJANGO_SERVE_SPA=1
   DJANGO_PUBLIC_ORIGIN=https://YOUR-SUBDOMAIN.ngrok-free.dev
   DJANGO_BEHIND_HTTPS_PROXY=1
   ```
3. `ngrok http 8000` — open the **ngrok HTTPS URL**, click through ngrok’s interstitial, then log in there (not on `localhost:5173`).

**Split dev** (Vite on `:5173` with `VITE_API_BASE` pointing at ngrok): session cookies are on the ngrok host; set `DJANGO_PUBLIC_ORIGIN` to that HTTPS origin for CORS in DEBUG.

**CSRF / origin errors:** With `DJANGO_DEBUG=1`, `localhost:5173` is trusted. For other hosts set `DJANGO_CSRF_TRUSTED_ORIGINS` or `DJANGO_PUBLIC_ORIGIN`.

**HTTPS mismatch:** Do not point `VITE_API_BASE` at `https://127.0.0.1:8000` unless Django serves TLS. Prefer the Vite proxy (empty base URL) or `http://127.0.0.1:8000`.

---

Built with React 19, TypeScript, Vite, and the React Compiler (see Vite template notes below if extending ESLint).
