# URL environment (APP_BASE_URL / API_BASE_URL)

## Production (recommended)

| Variable | Example | Purpose |
|----------|---------|---------|
| **APP_BASE_URL** | `https://pleerityenterprise.co.uk` | User-facing SPA (emails, Stripe redirects, magic links). |
| **API_BASE_URL** | `https://api.yourhost.com` | Public API origin for absolute links (e.g. order document download URLs in JSON). |
| **ENVIRONMENT** | `production` | Enables strict URL validation (HTTPS app URL; no conflicting app origins). |

## Legacy (compatibility only)

If `APP_BASE_URL` is unset, resolution falls back in order:  
`FRONTEND_PUBLIC_URL` → `PUBLIC_APP_URL` → `FRONTEND_URL` → `PORTAL_BASE_URL`.

If `API_BASE_URL` is unset: `BACKEND_URL` → `API_URL` → `BASE_URL` → `http://localhost:8000`.

**Do not** set multiple legacy app variables to **different** hosts in production — startup will fail.  
The same host with mixed `http://` and `https://` is treated as one origin (common with legacy env).

## Render (backend web service)

Render sets **`RENDER=true`**. The API defers Mongo connect, index creation, seeds, and the job scheduler until **after** the process binds to **`PORT`** (avoids “port scan timeout” while startup runs for minutes). Until then, most routes return **503**; **`/`** and **`/api/health`** still respond so the instance is reachable.

## Escape hatch

`SKIP_URL_VALIDATION=true` — disables production disagreement/HTTPS checks (emergency only).

## Frontend

`REACT_APP_BACKEND_URL` remains the frontend build variable pointing at the API (unchanged).
