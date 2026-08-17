# Commercial Controls — Step-up runtime 03

**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`  
**Operator:** `prosper@yopmail.com` / `ROLE_ADMIN` (JWT). Password is not recorded.

## Authentication preflight

Exactly one controlled staging login was performed before the suite.

| Result | Classification |
| --- | --- |
| `POST /api/auth/admin/login` → **200** | continue |
| Token reused for the API suite | valid Bearer |
| `ROLE_ADMIN` | proven in JWT claims |
| `commercial_entitlement_execute` | `requires_step_up: true`, `requires_confirmation: true` |

Not 401 / not 423. `AUTH_LOCK_EMAIL_MINUTES` was not bypassed.

## API step-up

| Check | Result | SHA |
| --- | --- | --- |
| Execute without `X-Step-Up-Token` | **403** `STEP_UP_REQUIRED` | `7c77391a` |
| `POST /api/auth/step-up/verify` with valid credential | **200**, `expires_in_seconds: 600` | `7c77391a` |
| One invalid step-up password | **401** (single attempt only) | `7c77391a` |
| Token TTL expiry | not elapsed within this window (default 10 minutes); leftover token still accepted once | `7c77391a` |

## UI (staging alias, bundle `main.c8b6a433.js`)

Client `33017032-afec-48cc-8102-30761bf49f75` (Alistair Campbell), Billing → Commercial Controls.

| Step | Evidence |
| --- | --- |
| Panel renders | Governance assessment, canonical/effective access, restored plan, exception, expiry, Stripe recon |
| Submit revoke | Execute dialog; Apply issues `POST .../execute` |
| `STEP_UP_REQUIRED` | **403** then password modal “Confirm your password” |
| Cancelled modal | Cancel closed the password dialog; exception remained `GRACE_PERIOD`; no mutation |
| Complete step-up | After circuit cooldown, verify **200**, execute **200** |
| Spinner | Button showed `Verifying…` then terminated; dialogs closed |
| Refresh without reload | Governance `GRACE_PERIOD` → `ACTIVE`; exception rows cleared; seven action buttons returned; audit `commercial_revoked` `2026-08-15T20:01:03` |

Network (UI session): execute 403, execute 403, step-up verify 200, step-up verify 200, execute 200.

## Runtime defect (do not treat as Suspend Billing authority)

Client circuit breaker `frontend/src/utils/apiRequestCircuit.js` counts **all HTTP 403** toward `CIRCUIT_FAILURE_THRESHOLD = 2`, including `STEP_UP_REQUIRED`. Cancel then retry opened the circuit for 90s (`Request paused after repeated failures. Try again shortly.`). The commercial action could not resume until cooldown. `resetApiCircuit` is not called on 200. Sequential UI executes in one session can therefore trip the circuit on the second `STEP_UP_REQUIRED`.

This is a **UI/API-client defect**, not a change to Suspend Billing commercial authority. No implementation change was made in this exercise.

## Timeout

Execute dialog uses `timeout: 60000`. Bundle minification does not keep the literal `timeout:60000`. API executes in this run completed in ~3–10s. Forced 60s hang was not generated.
