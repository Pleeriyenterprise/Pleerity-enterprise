# Admin Auth Client Consistency Hardening

**Programme:** ADMIN-AUTH-CLIENT-CONSISTENCY-HARDENING-01  
**Run tag:** `20260606T172720Z`  
**Classification:** `PARTIAL` (code + tests complete; staging browser pending frontend deploy)

## Root cause (recap)

`AdminNewsletterPage`, `AdminFAQPage`, and `AdminInsightsFeedbackPage` used `localStorage.getItem('token')` while `AuthContext` stores `auth_token`. Authenticated admin API calls returned 401; pages swallowed errors and rendered misleading empty states (e.g. "0 subscribers").

## PART 1 — Token usage audit

| Result | Detail |
|--------|--------|
| Legacy `token` key reads | **0** (cleared) |
| Canonical layer | `frontend/src/api/authStorage.js` |
| Axios interceptor | Uses `getAuthToken()` / `getContractorToken()` |

Artifact: `auth_token_usage_inventory.json`

## PART 2 — Centralized auth client

- `authStorage.js` — single token retrieval API
- `client.js` — interceptor wired to authStorage; exports `classifyAxiosError`, `ADMIN_FETCH_STATE`
- `adminAPI` — `listNewsletterSubscribers`, `listFaqsAdmin`, `listInsightsFeedback`, FAQ CRUD
- `useAuthenticatedQuery` hook — axios fetch with structured errors
- `adminFetchState.js` — loading / empty / auth / server / network classification
- `AdminFetchStatePanel` — operational error UI with retry + sign-in

Artifact: `auth_client_hardening_runtime.json`

## PART 3 — Admin page hardening

| Page | adminAPI | useAuthenticatedQuery | Error surface |
|------|----------|----------------------|---------------|
| AdminNewsletterPage | Yes | Yes | AdminFetchStatePanel |
| AdminFAQPage | Yes | Yes | Inline + save errors |
| AdminInsightsFeedbackPage | Yes | Yes | AdminFetchStatePanel |

Artifact: `admin_page_hardening_runtime.json`

## PART 4 — Newsletter dashboard closeout

| Check | Result |
|-------|--------|
| Public subscribe API | 200 |
| Admin API count | 9 → 10 |
| Kit sync | SYNCED |
| Duplicate | Already subscribed |
| Staging browser UI | Pending frontend deploy (old bundle) |
| Component unit test | Pass — renders rows; 401 shows auth error not empty |

Artifact: `newsletter_dashboard_closeout_runtime.json`

## PART 5 — Error visibility governance

- Fixed marketing admin pages: **SAFE**
- Remaining manual `fetch` + `auth_token` on contact/blog/catalogue pages: tracked (not `AUTH_DRIFT`)

Artifact: `admin_error_visibility_runtime.json`

## PART 6 — Regression

- `test_admin_auth_client_consistency.py`: **5 passed**
- Frontend: `authStorage`, `adminFetchState`, `AdminNewsletterPage` tests — **11 passed**

Artifact: `auth_client_regression_runtime.json`

## Classification

`PARTIAL` — blocker: `staging_browser_deploy` until frontend bundle with hardened pages is live on staging.

Harness: `backend/admin_auth_client_consistency_hardening_01_execute.py`
