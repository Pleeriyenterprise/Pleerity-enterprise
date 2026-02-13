# Blank screen fix — how to verify live

## 1. Get live evidence (you run these)

- **Console:** After opening https://order-fulfillment-9.emergent.host/login/client and logging in, open DevTools → Console. You should see:
  - `[CVP] REACT_APP_BACKEND_URL: <url>`
  - `[CVP] API request #1: /client/dashboard → <status>` (and #2, #3)
- **First failed request:** In Network tab, find the first request that fails (red, status 4xx/5xx or "failed"). Note: **URL**, **Status**, **Response body** (or "No response" for CORS/network).
- **Console error:** If the screen is blank, copy the **first red error** and its **stack trace**.

## 2. Verify the fix (no blank screen)

1. **Version:** `curl -s https://order-fulfillment-9.emergent.host/api/version` → JSON with `commit_sha` and `environment`.
2. **Login:** Go to `/login/client`, sign in with a test client.
3. **Dashboard:** You should land on `/app/dashboard` and see **one of**:
   - Full dashboard (header, nav, content), or
   - Same shell (header, nav) with an alert: "Session expired" (after redirect to login), "Not provisioned or action required" with Continue, "Cannot reach server" with backend URL, or a red error message. **No blank white screen.**
4. **Debug panel:** Add `?debug=1` to the URL (e.g. `/app/dashboard?debug=1`). A dark bar at the bottom should show Build SHA, Backend URL, and Last API error (if any).

## 3. If test client gets "Provisioning incomplete"

- **Backend:** As admin, call `PATCH /api/admin/billing/clients/{client_id}/test-provision` with body `{"onboarding_status": "PROVISIONED", "billing_plan": "PLAN_1_SOLO"}` (or PLAN_2_PORTFOLIO / PLAN_3_PRO). Then have the test client log in again.

## 4. Files changed (this fix)

- **frontend/src/api/client.js** — Log backend URL; track first 3 API requests (URL + status); set `window.__CVP_LAST_API_ERROR` for debug panel; export `API_URL`.
- **frontend/src/components/DebugPanel.js** — New: on-screen panel when `?debug=1` (build SHA, backend URL, last API error).
- **frontend/src/App.js** — `window.__CVP_BUILD_SHA`; import and render `DebugPanel`.
- **frontend/src/pages/ClientDashboard.js** — Import `API_URL`; `networkError` state; on no response set error to "Cannot reach server. Backend: ..."; safe error message when detail is object.
- **backend/routes/admin_billing.py** — `PATCH .../test-provision` to set test client `onboarding_status` and `billing_plan`.

(Existing: ErrorBoundary, 401→session_expired, 403 alerts, GET /api/version, build stamp.)
