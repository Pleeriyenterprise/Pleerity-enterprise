# P0-AUTHENTICATED-RUNTIME-403-ROOT-CAUSE-01

**Verdict:** `AUTHENTICATED_RUNTIME_RESTORED_WITH_CONDITIONS`  
**Run:** 20260707T100000Z  
**Evidence:** [P0_AUTHENTICATED_RUNTIME_403_EVIDENCE.json](./P0_AUTHENTICATED_RUNTIME_403_EVIDENCE.json)

---

## Executive summary

Authenticated 403 storms after successful login were caused by a **single systemic defect** in `_client_context_guard`: a coarse lifecycle block list denied all client APIs (including `/api/profile/me`) for non-terminal account states **before** Runtime Contract capability evaluation (`CAP_*`). Staging backend commit `ba79b17b` narrows that block to terminal bands only (`ARCHIVED`, `ACCOUNT_DELETED`).

The Vercel preview frontend (`pleerity-enterprise-9jjg`, bundle `main.be27b211.js`) is **not deployed from current develop** and still calls legacy `GET /client/entitlements`, lacks `getLifecycleRuntime` / `formatApiErrorDetail`, and therefore continues to produce entitlements 403 noise and React error #31 until redeployed.

This programme adds:

- Capability enforcement contract loads with `emit_events=False` (hot-path stability).
- `usePortfolioUsageContext` migrated off `/client/entitlements/context` to lifecycle-runtime plan material.
- Runtime contract `plan.max_properties` for governed upgrade copy.
- Targeted regression tests.

---

## Why login 200 but `/api/profile/me` 403?

| Stage | Login (`POST /auth/login`) | `/api/profile/me` |
|-------|---------------------------|-------------------|
| Portal user / password | Yes | Yes (via JWT) |
| Client provisioning | Yes | Yes (`client_route_guard`) |
| Coarse lifecycle block | No | **Yes (pre-ba79b17b)** |
| `CAP_PROFILE_VIEW` | No | Yes |

Login succeeds when portal credentials and provisioning are valid. Profile routes additionally pass `client_route_guard` → `_client_context_guard`. Between ILP-10 convergence and `ba79b17b`, `_blocked_lifecycle` included `READ_ONLY`, `SUSPENDED`, `CANCELLED_IMMEDIATE`, and `SUBSCRIPTION_EXPIRED`, returning governed `lifecycle_access_denied` **403** before any `CAP_*` check.

---

## First denial point

**File:** `backend/middleware/__init__.py` — `_client_context_guard`  
**Check:** `lifecycle_state in _blocked_lifecycle` (pre-fix)  
**HTTP:** 403 with `lifecycle_access_denied` payload from Lifecycle Response Authority

After `ba79b17b`, the first denial for healthy non-terminal accounts moves to per-capability evaluation (`CapabilityEnforcementService.evaluate`) only when policy genuinely denies the action.

---

## Runtime Contract (ACTIVE fixture evidence)

From `build_runtime_contract` ACTIVE test fixture:

| Field | Value |
|-------|--------|
| `lifecycle_state` | `ACTIVE` |
| `portal_mode` | `FULL_ACCESS` |
| Capability map size | ≥ 40 |
| `CAP_PROFILE_VIEW` | `ALLOW` |
| `CAP_DASHBOARD_VIEW` | `ALLOW` |
| `CAP_TODAY_VIEW` | `ALLOW` |
| `CAP_PROP_VIEW` | `ALLOW` |
| `CAP_DOC_VIEW` | `ALLOW` |
| `CAP_REPORT_VIEW` | `ALLOW` or plan-resolved |

---

## Why `/api/client/entitlements` still appeared

1. **Stale Vercel bundle** — probe shows `getEntitlements:` and `/client/entitlements` present; `getLifecycleRuntime` absent.
2. **Residual hook** — `usePortfolioUsageContext` called `getEntitlementsContext` on mount (removed in this programme).

Develop source no longer defines `getEntitlements` in `client.js`; legacy route remains on backend for transitional compatibility but is not a production consumer after this change.

---

## Why React error #31 persisted

Minified React #31 (`Objects are not valid as a React child`) occurred when governed 403 `detail` objects (`safe_to_retry`, `action`, `effective_semantic`) were passed directly into UI state/toasts. `formatApiErrorDetail` and related coercion exist on **develop** but are **missing from deployed bundle** `main.be27b211.js`.

---

## Conditions for full acceptance

1. **Redeploy** `pleerity-enterprise-9jjg` from current `develop` (must ship lifecycle runtime + error coercion).
2. **Re-run** authenticated endpoint matrix with the same user session.
3. Confirm no post-login 429 IP blocks (mitigated in `898cc8b9`).

---

## Tests

**Backend**

- `tests/test_p0_authenticated_runtime_403_root_cause_01.py` (8 passed)
- `tests/test_p0_staging_runtime_stabilization.py` (6 passed)

**Frontend**

- `src/hooks/usePortfolioUsageContext.test.js`
- `src/utils/p0StagingRuntimeStabilization.test.js`
- `src/utils/portalNotifications.test.js`

---

## Endpoint validation matrix (post-backend deploy)

After `ba79b17b` backend deploy, authenticated ACTIVE users should receive **200 or governed capability denial** (not coarse lifecycle 403) on:

- `/api/profile/me`
- `/api/client/lifecycle-runtime`
- `/api/client/session-runtime/status`
- `/api/client/dashboard`
- `/api/today/items`
- `/api/client/properties`
- `/api/client/requirements`
- `/api/documents`
- `/api/reports/available`
- `/api/billing/status`

Full green UX requires frontend redeploy per conditions above.
