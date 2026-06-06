# Admin Auth Client Consistency Hardening

**Programme:** ADMIN-AUTH-CLIENT-CONSISTENCY-HARDENING-01  
**Browser closeout:** ADMIN-AUTH-CLIENT-CONSISTENCY-BROWSER-CLOSEOUT-01  
**Hardening commit:** `b0d7bd41`  
**Final classification:** `VERIFIED_OPERATIONALLY`  
**Browser closeout run:** `20260606T174543Z`

## Root cause (recap)

`AdminNewsletterPage`, `AdminFAQPage`, and `AdminInsightsFeedbackPage` used `localStorage.getItem('token')` while `AuthContext` stores `auth_token`. Authenticated admin API calls returned 401; pages swallowed errors and rendered misleading empty states (e.g. "0 subscribers").

## Hardening delivered (`b0d7bd41`)

- `authStorage.js` — canonical token retrieval
- `client.js` interceptor uses `getAuthToken()` / `getContractorToken()`
- `useAuthenticatedQuery`, `adminFetchState`, `AdminFetchStatePanel`
- Marketing admin pages migrated to `adminAPI`

## Browser closeout — VERIFIED_OPERATIONALLY

### PART 1 — Deploy proof

| Check | Result |
|-------|--------|
| Frontend | `https://pleerityenterprise.co.uk` — 200 |
| API health | 200 |
| Main bundle hash | `db99e2f1` |
| `listNewsletterSubscribers` in bundle | Yes |
| `No subscribers yet` copy | Yes |
| `Session expired or not signed in` | Yes |
| Legacy `getItem('token')` | **Absent** |

Artifact: `admin_auth_browser_deploy_runtime.json`

### PART 2 — Newsletter dashboard browser

| Check | Result |
|-------|--------|
| UI subscriber count | **11** |
| Prior audit email visible | Yes |
| Kit Sync column | Yes |
| Export CSV | `newsletter_subscribers.csv` |
| Refresh | Preserves count |
| Misleading "0 subscribers" | **No** |

Artifact: `newsletter_dashboard_browser_closeout_runtime.json`

### PART 3 — Auth error visibility (invalid JWT)

| Page | Auth error shown | Retry/sign-in | Fake empty |
|------|------------------|---------------|------------|
| Newsletter | Yes | Yes | No |
| FAQ | Yes | Yes | No |
| Insights Feedback | Yes | Yes | No |

Artifact: `admin_auth_error_visibility_browser_runtime.json`

### PART 4 — Regression

- Backend `test_admin_auth_client_consistency.py`: **5 passed**
- Frontend auth tests: **11 passed**

Artifact: `admin_auth_browser_regression_runtime.json`

## Prior artefacts (hardening run `20260606T172720Z`)

- `auth_token_usage_inventory.json`
- `auth_client_hardening_runtime.json`
- `admin_page_hardening_runtime.json`
- `newsletter_dashboard_closeout_runtime.json` (API)
- `admin_error_visibility_runtime.json` (static)
- `auth_client_regression_runtime.json`

Harnesses:
- `backend/admin_auth_client_consistency_hardening_01_execute.py`
- `backend/admin_auth_client_consistency_browser_closeout_01_execute.py`
