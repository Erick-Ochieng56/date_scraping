# Ateric — Staff dashboard (React)

React + Vite + Tailwind (shadcn Nova) + TanStack Query. This SPA is the **staff** (operator/tools) UI. The **admin** dashboard is the Django **template** app at `/dashboard/` on the backend.

API calls use **`/dashboard/api/*`** (proxied in dev to `http://127.0.0.1:8000` — see `vite.config.ts`).

## Dev

1. Start Django: `python manage.py runserver` (from `backend/`, port **8000**), **or** HTTPS dev server, e.g.  
   `python manage.py runserver_plus --cert-file cert.pem` (often **https://127.0.0.1:8000**).
2. `npm install` then `npm run dev` (Vite **5173**). If Django is HTTPS, copy `frontend/.env.example` lines into `.env` and set  
   **`VITE_DJANGO_PROXY_TARGET=https://127.0.0.1:8000`** so the Vite proxy accepts your self-signed cert (`secure: false` is applied automatically).
3. **Staff:** open `http://localhost:5173/login` (or `http://127.0.0.1:5173/login` — use the **same host** as your API/proxy so the session cookie is set correctly). Sign in with a user created via `create_staff_user` (in the portal group, not Django `is_staff`).
4. **Admins:** use the Django HTML dashboard at `/dashboard/` (and `/admin/`). They cannot use the SPA login; the app will show a message with a link to Django.

### RBAC (backend)

- Run migrations so the portal group exists (default name **`scraper`**, `dashboard` migration `0003_scraper_group`).
- **Admin:** `python manage.py createsuperuser`
- **Staff (React):** `python manage.py create_staff_user` — same prompts and `--noinput` / env vars as `createsuperuser`, but creates a normal user in the portal group (no Django admin access).

```bash
cd backend && python manage.py create_staff_user
```

Optional: copy `.env.example` → `.env` and set `VITE_API_BASE` if the API is on another origin (production).

### Troubleshooting (403 CSRF: “Origin checking failed … localhost:5173”)

Django must trust the SPA’s origin. With **`DJANGO_DEBUG=1`**, `leads_app/settings.py` already adds `http://localhost:5173` and `http://127.0.0.1:5173`. If you use another host/port or `DEBUG=0`, set e.g. `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-spa.example.com`.

### Troubleshooting (Django console: “HTTPS but only supports HTTP” / “Bad request version”)

1. **Do not** point `VITE_API_BASE` at `https://127.0.0.1:8000` unless Django is actually serving TLS on 8000 (normally it is not). Use the Vite proxy (empty base URL) or `http://127.0.0.1:8000`.
2. If `DJANGO_DEBUG=0`, avoid `DJANGO_SECURE_SSL_REDIRECT=1` for local HTTP — Django will 301 to `https://` and the next hop will fail on `runserver`. Use `DJANGO_DEBUG=1` for local dev, or set `DJANGO_SECURE_SSL_REDIRECT=0` (default when unset in `settings.py`).

---

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is enabled on this template. See [this documentation](https://react.dev/learn/react-compiler) for more information.

Note: This will impact Vite dev & build performances.

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
