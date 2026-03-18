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

**Do not** set multiple legacy app variables to **different** origins in production — startup will fail.

## Escape hatch

`SKIP_URL_VALIDATION=true` — disables production disagreement/HTTPS checks (emergency only).

## Frontend

`REACT_APP_BACKEND_URL` remains the frontend build variable pointing at the API (unchanged).
