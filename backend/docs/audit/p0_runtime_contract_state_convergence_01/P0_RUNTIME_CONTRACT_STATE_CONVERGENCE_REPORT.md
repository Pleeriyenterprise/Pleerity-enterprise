# P0 — Runtime Contract Validation & State Convergence

**Programme:** P0-RUNTIME-CONTRACT-STATE-CONVERGENCE-01  
**Date:** 2026-07-07  
**Staging backend:** `37de7209` (pre-fix deploy)  
**Affected account (evidence):** `aigbochieprosperity@gmail.com` / `24e15552-df1e-4b1e-943d-82832554e1a8`

---

## Executive summary

Staging probes proved a **split authority chain**: session validation successfully resolved a Runtime Contract (response headers carried `X-Lifecycle-Runtime-Version: 450114548`), while every CAP_* evaluation returned **`runtime_unavailable`** with null lifecycle — blocking `/client/lifecycle-runtime`, `/profile/me`, `/client/properties`, and all governed data APIs.

This is not a page bug. It is **duplicate contract resolution** without request-scoped sharing, plus **lifecycle fact drift** on the account record.

---

## Proven failure chain (staging)

| Step | Result |
|------|--------|
| Login | 200 |
| `GET /client/lifecycle-runtime` | 403 `runtime_unavailable` |
| `GET /profile/me` | 403 `runtime_unavailable` |
| `GET /client/portal-context` | 403 `runtime_unavailable` (required `CAP_DASHBOARD_VIEW`) |
| `GET /client/properties` | 403 `runtime_unavailable` |

Account facts (admin API):

- `subscription_status`: ACTIVE  
- `onboarding_status`: PROVISIONED  
- `client_lifecycle_status`: ACTIVE  
- **Stale** `lifecycle_status`: `pending_payment` (intake funnel mirror)  
- **Missing** `client_billing` row  
- Stripe billing sync blocked: `STRIPE_CUSTOMER_MODE_DRIFT` (409)

---

## Root causes

### 1. Request-scoped contract not shared (P0 architectural)

- `apply_session_runtime_validation` resolved the contract once per request.
- `CapabilityEnforcementService.evaluate()` resolved again independently.
- On staging the second resolution path returned `RUNTIME_UNAVAILABLE` while the first succeeded (headers proved contract materialisation).

**Fix:** Resolve once in `apply_session_runtime_validation`, attach to `request.state.runtime_contract` and `user.runtime_contract`, and pass through all CAP_* evaluation.

### 2. Lifecycle bootstrap chicken-and-egg

- `GET /client/lifecycle-runtime` required `CAP_PROFILE_VIEW` before returning the contract that defines capabilities.

**Fix:** Return contract after `client_route_guard` only (bootstrap endpoint).

### 3. Stale legacy lifecycle mirror

- Resolver treated `lifecycle_status: pending_payment` as authoritative even when `PROVISIONED + ACTIVE subscription + client_lifecycle_status ACTIVE`.

**Fix:** Skip legacy pending_payment band when provisioned active subscription/org facts are present.

### 4. Frontend authority drift

- `GOVERNED_FALLBACK` claimed “permissions unchanged” with empty capabilities.
- 403 denial path set partial runtime → `runtimeAvailable=true` with empty capabilities.
- Portal status line fetched independently via `portal-context` (CAP-gated).
- Profile edit allowed when `runtimeAvailable` false positives.

**Fix:** Honest unavailable copy; `runtimeAvailable` requires capabilities map; portal trust waits for runtime; profile capabilities require `runtimeAvailable`.

### 5. Data / ops blocker (genuine, documented)

- `client_billing` never materialised — admin sync returns `STRIPE_CUSTOMER_MODE_DRIFT`.
- Requires Stripe mode governance remediation (outside this code change).

---

## Code changes (develop)

**Backend**

- `middleware/session_runtime.py` — single contract resolve + attach  
- `services/account_session_runtime_service.py` — accept preloaded contract  
- `middleware/capability_gating.py` — evaluate from attached contract  
- `routes/client_lifecycle_runtime.py` — bootstrap without CAP gate  
- `routes/client.py` — portal-context guard-only (authenticated shell metadata)  
- `routes/profile.py` — evaluate from attached contract  
- `services/account_lifecycle_state_resolver.py` — stale pending_payment precedence  
- `services/account_capability_enforcement.py` — richer load failure logging  

**Frontend**

- `contexts/LifecycleRuntimeContext.js` — unavailable semantics  
- `components/ClientPortalLayout.jsx` — portal trust gated on runtime  
- `utils/accountCapabilityAccess.js` — profile caps require runtime  

**Tests**

- `tests/test_p0_runtime_contract_state_convergence_01.py`

---

## Expected post-deploy behaviour (ACTIVE account)

- `GET /client/lifecycle-runtime` → 200 with full contract, `lifecycle_state: ACTIVE`  
- CAP_* checks use same contract → profile/properties/requirements load  
- No “permissions unchanged” banner during true outages  
- Portal status line loads after runtime (not in parallel failure mode)

---

## Remaining ops action

Run Stripe mode verification + `POST /admin/billing/clients/{id}/sync` for accounts missing `client_billing` to remove `missing_billing_record` warnings and align billing mirrors.
