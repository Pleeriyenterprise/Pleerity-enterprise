# Intake + Checkout Flow Audit — Enterprise Launch Readiness

Evidence-based audit of the Compliance Vault Pro intake wizard and Stripe checkout handoff. All claims cite file:line.

---

## 1. Current Implementation (Evidence)

### 1.1 Intake wizard (frontend)

| Area | Location | Behavior |
|------|----------|----------|
| Entry, steps, plan limits | `frontend/src/pages/IntakePage.js` | Steps 1–5: Your Details, Select Plan, Properties, Preferences, Review. `PLAN_LIMITS` (lines 38–47) Solo=2, Portfolio=10, Pro=25. `PLAN_NAMES` for display. |
| Add property + cap (UI) | `IntakePage.js:288–323` | `addProperty()` checks `newCount > maxProps` (PLAN_LIMITS[formData.billing_plan]); sets `propertyLimitError` and toasts; optionally calls `intakeAPI.validatePropertyCount(plan, newCount)`. |
| Upgrade during intake | `IntakePage.js:819–823`, `UpgradePrompt.js:224–240` | Step3 `handleUpgrade` only does `setFormData({ ...formData, billing_plan: upgradePlan.code })` and `setPropertyLimitError(null)`. `PropertyLimitPrompt` with `switchPlanOnly={true}`: on "Upgrade" calls `onUpgrade()` only, no navigate — plan selection only, no entitlement. |
| Submit + checkout | `IntakePage.js:393–438` | `handleSubmit`: validateStep(4) → `intakeAPI.submit(submitData)` → `intakeAPI.createCheckout(client_id)`. Redirect only if `checkoutResponse?.data?.checkout_url` present; else set error. Catches errors and maps `PROPERTY_LIMIT_EXCEEDED`, `CHECKOUT_FAILED`, `CHECKOUT_URL_MISSING` to user message. |
| Review step | `IntakePage.js:1665–1877` | Step5Review: shows Your Details, Selected Plan (name, max_properties, price, setup fee), Properties (count of maxProps, list), Preferences (doc method + staged upload filenames when UPLOAD), Payment summary. Fetches `GET /api/intake/uploads/list/{intakeSessionId}` when doc method is UPLOAD; displays "Staged uploads: …" or "No files uploaded yet. You can add documents after account setup." |

### 1.2 Backend intake

| Area | Location | Behavior |
|------|----------|----------|
| Property limit at submit | `backend/routes/intake.py:667–705` | `submit_intake`: resolves `plan_code` from `data.billing_plan`, calls `plan_registry.check_property_limit(plan_code, len(data.properties))`. If not allowed → **403** with `error_code: PROPERTY_LIMIT_EXCEEDED`, message, current_limit, upgrade_to, etc. |
| Validate property count | `backend/routes/intake.py:325–388` | `POST /api/intake/validate-property-count`: body `plan_id`, `property_count`. Uses `plan_registry.check_property_limit`; returns `allowed`, `error`, `upgrade_to`, etc. |
| Checkout session | `backend/routes/intake.py:1026–1095` | `POST /api/intake/checkout?client_id=`. Loads client (billing_plan, email, contact_email). `customer_email = client.get("contact_email") or client.get("email")`. Calls `stripe_service.create_checkout_session(...)`. Returns `checkout_url`, `session_id`. If no URL → 502 with `CHECKOUT_URL_MISSING`. Catches `ValueError` → 400 with `CHECKOUT_FAILED`; other → 500 with structured detail. |
| Stripe session creation | `backend/services/stripe_service.py:33–148` | Uses `plan_registry.get_plan`, `get_stripe_price_ids`; subscription + onboarding line items; metadata `client_id`, `plan_code`; success/cancel URLs from origin. Returns `checkout_url`, `session_id`. On StripeError raises ValueError. |
| Pre-payment vs post-payment | `backend/services/stripe_webhook_service.py` | Client and properties are created at **submit** (intake); **entitlements** (subscription_status, provisioning) are applied only after **checkout.session.completed** (and subscription webhooks). No entitlement grant from frontend plan selection. |
| Intake uploads → client | `backend/routes/intake.py:851–854`, `provisioning.py:218–221`, `intake_upload_migration.py` | Submit calls `_reconcile_intake_documents` for legacy intake upload-document path. CVP flow uses `intake_uploads` collection; `migrate_intake_uploads_to_vault(client_id)` runs during provisioning to attach CLEAN intake uploads to client documents. |

### 1.3 Document upload policy

| Decision | Implementation |
|----------|----------------|
| Option A (launch) | Intake uploads are **optional**. User can proceed with "Upload here" and zero files. Review shows "No files uploaded yet. You can add documents after account setup in your dashboard." No server-side requirement for ≥1 file when method is UPLOAD. |
| Staging → client | Intake uploads stored by `intake_session_id` (e.g. `intake_uploads`); after payment and provisioning, `migrate_intake_uploads_to_vault(client_id)` copies CLEAN uploads into vault and links to client/properties. |

---

## 2. Changes Made (Summary)

| Goal | Change | File:line (or file) |
|------|--------|----------------------|
| A) Upgrade during intake only changes plan | `PropertyLimitPrompt` accepts `switchPlanOnly`; when true, click only calls `onUpgrade()`, no navigate. Intake passes `switchPlanOnly`. | `UpgradePrompt.js:224–240`; `IntakePage.js:868` |
| A) API bypass returns 403 | Submit property-limit violation → `HTTP_403_FORBIDDEN` with `error_code: PROPERTY_LIMIT_EXCEEDED`. | `intake.py:696` |
| B) No entitlement pre-payment | Already true: entitlements set in Stripe webhook + provisioning. Documented in audit. | — |
| C) Optional upload + review note | Review shows staged filenames from `GET /api/intake/uploads/list/{intakeSessionId}`; when UPLOAD and 0 files, shows note that user can add later. | `IntakePage.js:1672–1682`, 1834–1842 |
| D) Review full summary | Property count shown as "X of Y"; plan + cap; preferences + staged upload filenames. | `IntakePage.js:1736–1738`, 1834–1842 |
| E) Checkout crash fix | Backend: `customer_email` fallback to `client.get("email")`; return 502 if no `checkout_url`; ValueError→400, other→500 with `error_code`/`message`. Frontend: redirect only if `checkout_url` present; catch and display structured error (PROPERTY_LIMIT_EXCEEDED, CHECKOUT_FAILED, CHECKOUT_URL_MISSING). | `intake.py:1050–1095`; `IntakePage.js:417–434` |

---

## 3. Property Gating (Server-Side)

| Check | Where | Evidence |
|-------|--------|----------|
| Submit: property count vs plan | Before creating client/properties | `intake.py:681–705` — `plan_registry.check_property_limit(plan_code, len(data.properties))`; 403 if not allowed. |
| Validate-property-count | API for UI | `intake.py:357–374` — same `check_property_limit`; returns allowed/error/upgrade_to. |
| Post-login property create/bulk | Already enforced | `routes/properties.py` — `plan_registry.enforce_property_limit(client_id, current_count + n)` (see FULL_SYSTEM_PRICING_CAPABILITY_AUDIT). |
| Intake does not grant entitlement | Submit only creates client + properties; onboarding_status remains until payment + webhook | `intake.py:752–763` (client insert); provisioning and status updates in stripe_webhook_service + provisioning_runner. |

---

## 4. Checkout Flow (Happy Path + Failure)

| Step | Behavior |
|------|----------|
| 1. Submit | POST /api/intake/submit with valid data → 200, `client_id`, `next_step: "checkout"`. |
| 2. Create session | POST /api/intake/checkout?client_id=… → 200, `checkout_url` (Stripe URL), `session_id`. |
| 3. Redirect | Frontend sets `window.location.href = checkout_url`. |
| 4. Failure (no URL) | Backend returns 502 + CHECKOUT_URL_MISSING; frontend does not redirect, shows message. |
| 5. Failure (Stripe/ValueError) | Backend returns 400/500 + CHECKOUT_FAILED; frontend shows detail.message. |
| 6. Failure (submit 403) | Property limit exceeded → 403 + PROPERTY_LIMIT_EXCEEDED; frontend shows plan/property error. |

---

## 5. Tests (Added / Existing)

| Test | Location | Coverage |
|------|----------|----------|
| Intake property cap enforced (API) | `tests/test_intake_wizard.py` | `test_submit_intake_enforces_plan_1_property_limit`: Solo + 3 properties → 403, detail.error_code PROPERTY_LIMIT_EXCEEDED. |
| Intake Portfolio over cap → 403 | `tests/test_intake_wizard.py` | `test_submit_intake_rejects_6_properties_for_plan_2_5`: PLAN_2_5 + 11 properties → 403. |
| Validate property count | `tests/test_iteration23_plan_structure.py`, `test_iteration24_frontend_integration.py` | validate-property-count enforces limits. |
| Checkout returns URL (happy path) | `tests/test_intake_wizard.py` | `test_checkout_returns_checkout_url_on_success`: submit then checkout → 200, checkout_url and session_id present. |
| Checkout failure (client not found) | `tests/test_intake_wizard.py` | `test_checkout_returns_404_for_invalid_client`: invalid client_id → 404, detail.error_code CLIENT_NOT_FOUND. |
| Checkout creates Stripe session | `tests/test_intake_wizard.py` | `test_checkout_creates_stripe_session`: full flow; Stripe URL in response. |
| Switching plan updates cap (UI) | Manual / E2E | Step 3 "Upgrade to Portfolio" only updates billing_plan; cap becomes 10; no redirect. |

---

## 6. Checklist — Enterprise Behavior

- [x] **A) Property gating during intake** — UI blocks add over cap; validate-property-count and submit enforce server-side; 403 on bypass. Upgrade during intake only changes plan selection (`switchPlanOnly`).
- [x] **B) Pre-payment vs post-payment** — No entitlements from frontend; provisioning and subscription status only after Stripe payment + webhook.
- [x] **C) Document upload** — Optional; review shows staged filenames or "add later" note; intake_uploads migrated to vault on provisioning.
- [x] **D) Review step** — User details, plan, property count + cap, property list, preferences, staged upload filenames.
- [x] **E) Stripe checkout** — Backend returns checkout_url; email fallback; structured errors; frontend redirects only when URL present and handles errors without crash.

---

## 7. Debugging “Proceed to Payment” failures (request_id + env)

### Using request_id to match frontend and backend

1. **Browser**: When checkout fails, the Step 5 alert shows “Payment setup failed. Reference: \<request_id\>” (or “Reference: \<request_id\>” in small text). Copy the `request_id` (UUID).
2. **Backend logs**: Search server logs for that `request_id`. All checkout error responses and log lines include it, e.g.  
   `Checkout client not found client_id=... request_id=<uuid>`  
   `Checkout invalid origin request_id=<uuid> origin=...`  
   `Checkout validation/Stripe error request_id=<uuid>: ...`  
   `Stripe session missing checkout_url ... request_id=<uuid>`  
   `Checkout creation error for client ... request_id=<uuid>: ...`
3. **Frontend (dev only)**: With `NODE_ENV !== 'production'` or `window.__CVP_DEBUG`, the API client logs intake submit/checkout requests and responses to `console.debug` with `method`, `url`, `status`, and when present `error_code` and `request_id`. Use these to see which step failed (submit vs checkout) and the exact status and detail.

### Required environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| **REACT_APP_BACKEND_URL** | Frontend (build) | Backend base URL for API calls. If unset, the app uses relative `/api` (same-origin or proxy). Set in deployed env so the frontend reaches the correct backend. |
| **FRONTEND_ORIGIN** | Backend | Base URL for Stripe success/cancel redirects when the `Origin` header is missing or invalid (e.g. server-to-server). Example: `https://app.example.com`. |
| **STRIPE_API_KEY** | Backend | Stripe secret key. If missing or empty, checkout returns 400 CHECKOUT_FAILED with message “STRIPE_API_KEY is not set”. No placeholder default. |
| **Plan Stripe price IDs** | Backend (plan_registry) | Each plan must have `subscription_price_id` (and optionally `onboarding_price_id`) in the plan registry. Missing price IDs cause Stripe errors and 400 CHECKOUT_FAILED. |

At startup the backend logs: STRIPE_API_KEY set/missing and, per plan, subscription_price_id (and onboarding_price_id) so misconfiguration is visible in logs.
