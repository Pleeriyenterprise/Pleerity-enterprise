# Blank Screen After Client Login — Debug Guide & Patches

**Live URL:** https://order-fulfillment-9.emergent.host  
**Client login path:** `/login/client`  
**Dashboard after login:** `/app/dashboard`

---

## Root cause + Fix + How verified (summary)

- **Root cause (inferred from code):** The blank screen can be caused by (1) **401** on the first API call after login → redirect to `/login` with no “session expired” message; (2) **403** (e.g. provisioning incomplete, password not set) with no dedicated UI; (3) an **uncaught React error** (no Error Boundary) so the app crashes to a blank screen; (4) wrong **API base URL** or **CORS** so requests fail and behaviour is unclear.
- **Fix applied:**  
  - **Error Boundary** wraps the app so any render error shows “Something went wrong” + “Go to sign in” / “Refresh” instead of a blank screen.  
  - **401:** Redirect to `/login?session_expired=1`; Portal selector and Client login show “Session expired. Please sign in again.”  
  - **403:** Dashboard shows explicit alerts: “Access restricted by plan”, “Account not provisioned properly”, or “Not provisioned or action required” with a “Continue” button to `X-Redirect` (e.g. `/onboarding-status`, `/set-password`).  
  - **Dashboard shell** always renders (header, nav, main) once loading is done; errors show in alerts, not a blank page.  
  - **Debug:** Console logs `[CVP] API base URL: <url>` once; dashboard footer shows build stamp when `REACT_APP_BUILD_SHA` is set.
- **How to verify:** See **Verification checklist** below. Confirm deployed SHA via `GET /api/version`; log in as test client and confirm either dashboard content or one of the explicit alerts (never a blank screen).

---

## 1. Required First Answers (must be filled with live evidence)

These **cannot** be determined from code alone. You (or someone with access to the live site and Emergent) must provide:

| # | Question | How to get the answer |
|---|----------|------------------------|
| **1** | **What commit SHA is currently deployed on Emergent live?** | (A) Emergent dashboard / deployment history, or (B) After deploying the new backend: `GET https://order-fulfillment-9.emergent.host/api/version` → use `commit_sha` from response. |
| **2** | **What is the very first failed network request after client login?** | Browser DevTools → Network tab → log in at `/login/client` → go to `/app/dashboard` → find the first request with status 4xx/5xx or (failed). Note: URL, method, status, response body. |
| **3** | **What is the console error when the blank screen occurs?** | Browser DevTools → Console tab → reproduce login → copy the first red error and full stack trace. |

If the live deployment is **not** on the latest `main` SHA:

- In Emergent: trigger a redeploy from the connected repo (e.g. redeploy from `main` or from the specific commit).
- Ensure build env vars (see below) are set so that the deployed backend has `GIT_COMMIT_SHA` and the frontend has `REACT_APP_BUILD_SHA` (optional but recommended).

---

## 2. Root Cause Summary (code-based analysis)

- **Dashboard flow:** After client login, the app navigates to `/app/dashboard`, which mounts `ClientDashboard`. The component immediately calls `GET /api/client/dashboard` (and in parallel `/profile/notifications`, `/client/compliance-score`, `/client/compliance-score/trend`). Only the dashboard request drives `loading` and `error`; the others fail silently.
- **Possible causes of a blank screen (no speculation; confirm with answers 1–3):**
  - **401 on first request:** The axios interceptor in `frontend/src/api/client.js` redirects to `/login` on any 401. If the **first** request after login is 401 (e.g. token not sent, wrong backend URL, or backend rejecting the token), the user is sent to `/login` (portal selector), which a client user might describe as “blank” or wrong page.
  - **403 (e.g. provisioning incomplete):** `client_route_guard` returns 403 with "Provisioning incomplete" and `X-Redirect: /onboarding-status` when `onboarding_status !== PROVISIONED`. The frontend did not previously show a dedicated “Access restricted” / “Not provisioned” UI, so a generic error or missing handling could contribute to a bad experience.
  - **500 / network / CORS:** If the first request fails with 500, network error, or CORS, the dashboard sets `error` and `loading = false`. The UI is designed to still render (header, nav, error alert). A blank screen would then imply either a **React throw** (e.g. missing optional chaining somewhere) or an **error boundary** that renders nothing.
- **Plan gating:** `GET /api/client/dashboard` does **not** use plan/feature gating; it only uses `client_route_guard` (auth, active, password set, client exists, provisioning status). So plan codes are unlikely to be the direct cause of the dashboard call failing, unless the failure is on a **different** first request (e.g. compliance-score or notifications) and that request triggers a 403 and an unhandled path in the UI.

**Conclusion:** The **exact** root cause depends on (1) deployed SHA, (2) first failed request (URL + status + body), and (3) console error. The patches below add a version endpoint, build stamp, and defensive UI so that plan/provisioning issues show an explicit message instead of a blank screen, and so deployment can be verified.

---

## 3. Plan Gating (Goal A) — Reference

### 3.1 Plan codes and where they are stored

| Storage | Collection / location | Field(s) |
|--------|------------------------|----------|
| **Primary** | `clients` | `billing_plan` (e.g. `"PLAN_1_SOLO"`, `"PLAN_2_PORTFOLIO"`, `"PLAN_3_PRO"`) |
| **Billing** | `client_billing` (or equivalent) | `current_plan_code` |
| **Legacy** | Some code paths still read `plan_code` on client (e.g. auth enablement event); canonical source is `billing_plan`. |

### 3.2 Single source of truth for gating

- **File:** `backend/services/plan_registry.py`  
- **Runtime gating:** `backend/middleware/feature_gating.py` (uses `plan_registry` + `client.billing_plan` and subscription status).  
- **Routes** that enforce features use `plan_registry.enforce_feature(...)` (e.g. in `client.py`, `reports.py`, `documents.py`, `calendar.py`, `webhooks_config.py`).  
- **`GET /api/client/dashboard`** does **not** call `enforce_feature`; it only uses `client_route_guard`.

### 3.3 Plan tiers and features (summary)

| Plan code | Max properties | Enabled (examples) | Disabled (examples) |
|-----------|-----------------|----------------------|----------------------|
| **PLAN_1_SOLO** | 2 | compliance_dashboard, compliance_score, compliance_calendar, email_notifications, multi_file_upload, score_trending, ai_extraction_basic | zip_upload, reports_pdf, reports_csv, scheduled_reports, sms_reminders, tenant_portal, webhooks, api_access, white_label_reports, audit_log_export, ai_extraction_advanced, extraction_review_ui |
| **PLAN_2_PORTFOLIO** | 10 | Solo + zip_upload, reports_*, scheduled_reports, sms_reminders, tenant_portal, ai_extraction_advanced, extraction_review_ui | webhooks, api_access, white_label_reports, audit_log_export |
| **PLAN_3_PRO** | 25 | All features | — |

Full matrix: `backend/services/plan_registry.py` → `FEATURE_MATRIX`.

### 3.4 Where features are enforced

- **Backend:** Routes that use `require_feature("...")` or `plan_registry.enforce_feature(...)` return 403 / feature-disabled when the plan does not allow the feature.  
- **Frontend:** No central plan-driven UI gating was identified; optional hiding of features by plan would be in individual pages/components. The new ClientDashboard alerts (“Access restricted by plan”, “Account not provisioned”) improve clarity when the backend returns 403 or when plan data is missing.

---

## 4. Exact Code Changes (file-by-file)

### Backend

- **`server.py`**
  - Added `GET /api/version` returning `{ "commit_sha": "<from GIT_COMMIT_SHA or BUILD_SHA>", "environment": "<ENVIRONMENT>" }` for deployment verification.

### Frontend

- **`App.js`**
  - Log build stamp to console when `REACT_APP_BUILD_SHA` is set. Wrap app content in **ErrorBoundary** so render errors show fallback UI instead of blank screen.
- **`components/ErrorBoundary.js`** (new): Class component with componentDidCatch; fallback "Something went wrong" + Go to sign in / Refresh.
- **`api/client.js`**: Log API base URL once `[CVP] API base URL: ...`; on 401 redirect to `/login?session_expired=1`.
- **`PortalSelectorPage.js`** / **`ClientLoginPage.js`**: When `?session_expired=1` show "Session expired. Please sign in again."
- **`ClientDashboard.js`**
  - Added `restrictReason`: `'plan' | 'not_provisioned' | 'provisioning_incomplete'` and `redirectPath` (from 403 `X-Redirect`). 403 provisioning/password not set shows "Not provisioned or action required" + Continue.
  - (Existing) `restrictReason` state: `'plan' | 'not_provisioned' | null`.
  - In `fetchDashboard` catch: if status is 403 and detail mentions plan/feature/entitlement/restricted, set `restrictReason = 'plan'`.
  - In `fetchDashboard` success: if `client` exists and has no `billing_plan` and no `plan_code`, set `restrictReason = 'not_provisioned'`.
  - Rendered two explicit alerts (no blank screen):
    - **Access restricted by plan:** message + “Contact support” link (`data-testid="alert-restricted-by-plan"`).
    - **Account not provisioned properly:** message + “Contact support” link (`data-testid="alert-not-provisioned"`).
  - Footer: show “Build: &lt;REACT_APP_BUILD_SHA&gt;” when `REACT_APP_BUILD_SHA` is set (`data-testid="build-stamp"`).

### Tests

- **`backend/tests/test_version_and_client_dashboard.py`** (new)
  - `TestVersionEndpoint`: GET `/api/version` returns 200 with `commit_sha` and `environment`; `commit_sha` is a string.
  - `TestClientDashboardShellShape`: Asserts the dashboard response contract (client, properties, compliance_summary with required keys).

- **`backend/tests/test_plan_registry_gating.py`**
  - `test_feature_matrix_honored_per_plan`: One test per plan (Solo, Portfolio, Pro) asserting enabled/disabled features from the registry.

---

## 5. How to Verify on Live

1. **Deployed SHA**  
   - `GET https://order-fulfillment-9.emergent.host/api/version`  
   - Expect: `200`, body with `commit_sha` (string) and `environment`.

2. **Health**  
   - `GET https://order-fulfillment-9.emergent.host/api/health`  
   - Expect: `200`, `status: "healthy"`.

3. **Client login → dashboard**  
   - Open DevTools (Network + Console).  
   - Go to `https://order-fulfillment-9.emergent.host/login/client`, log in with a test client.  
   - Confirm redirect to `/app/dashboard`.  
   - Check: first failed request (URL, method, status, body) and first console error.  
   - After patches: you should see either the dashboard content or one of the explicit alerts (restricted by plan / not provisioned) instead of a blank screen.

4. **Build stamp**  
   - If `REACT_APP_BUILD_SHA` is set at build time: footer on client dashboard shows “Build: …” and console shows `[CVP] Build SHA: …`.

---

## 5b. Verification checklist (exact steps and expected results)

### Step 1 — Confirm deployed version
- **Action:** Open `https://order-fulfillment-9.emergent.host/api/version` in browser or curl.
- **Expected:** `200`, JSON: `{ "commit_sha": "<string>", "environment": "<string>" }`.
- **Note:** If you cannot access it (CORS/blocked), use Emergent deployment history for the SHA.

### Step 2 — What you should see in the UI after client login
- **Action:** Go to `/login/client`, sign in with a test client, land on `/app/dashboard`.
- **Expected (no blank screen):** Either full dashboard, or dashboard shell with one of: "Session expired" (after redirect to login), "Not provisioned or action required" + Continue, "Access restricted by plan", "Account not provisioned properly", or red error alert. If a React error occurs: Error Boundary shows "Something went wrong" + Go to sign in / Refresh.

### Step 3 — Requests: 200 / 403 / 401
- With valid token: `GET /api/client/dashboard` → 200 (provisioned) or 403 (provisioning incomplete / password not set).
- Without token: `GET /api/client/dashboard` → 401.
- Plan-gated routes: Solo client calling a Pro-only feature → 403.

### Step 4 — Confirm gating per plan (no DB edits)
- Log in as test client per plan; call `GET /api/client/plan-features` (with auth). Check `features` match plan (e.g. Solo: `reports_pdf: false`, Pro: `webhooks: true`). Or in UI, as Solo try a gated feature and see 403 or "Access restricted" message.

### Step 5 — Debug on live
- Console: one log `[CVP] API base URL: <url>`. If `(not set)`, fix `REACT_APP_BACKEND_URL`.
- Network: first request after login to `/api/client/dashboard` — check URL and status.

---

## 6. Emergent Environment Variables (exact names and types, no secrets)

Set these in Emergent for the **backend** (so `/api/version` and health are correct):

| Variable | Type | Purpose |
|----------|------|---------|
| `GIT_COMMIT_SHA` | string | Commit SHA of deployed code (e.g. from CI). Used by `GET /api/version`. |
| `BUILD_SHA` | string | Fallback if `GIT_COMMIT_SHA` is not set. |
| `ENVIRONMENT` | string | e.g. `production` / `staging`. Returned by `/api/health` and `/api/version`. |

For the **frontend** build (optional but recommended):

| Variable | Type | Purpose |
|----------|------|---------|
| `REACT_APP_BACKEND_URL` | string (URL) | Must point to the live backend (e.g. `https://order-fulfillment-9.emergent.host` or the API host you use). Wrong value causes wrong-origin API calls and can cause 401/CORS/blank. |
| `REACT_APP_BUILD_SHA` | string | Build/deploy stamp shown in footer and console. |

**Critical:** If the blank screen is due to API base URL or CORS, ensure `REACT_APP_BACKEND_URL` matches the backend that actually serves the app (same origin or allowed CORS). Confirm with the first failed request URL in the Network tab.
