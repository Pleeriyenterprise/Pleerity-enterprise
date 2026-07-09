# P0-BILLING-RECOVERY-AUTHORIZATION-BLOCKER-01

**Verdict:** `BILLING_RECOVERY_AUTHORIZATION_RESTORED_WITH_CONDITIONS`

**Date:** 2026-07-08  
**Scope:** develop / staging only (no production)

## Root cause

Investigation shows billing recovery was **not blocked by CAP_* denial** on staging for recovery-state accounts. The Runtime Contract already grants `CAP_BILLING_*` and `CAP_SUB_MANAGE` as `ALLOW` for `SUSPENDED`, `BILLING_RECOVERY`, `READ_ONLY`, and related recovery lifecycles.

Actual blockers were layered:

| Layer | Symptom | Cause |
|-------|---------|-------|
| Step-up | `403` `STEP_UP_REQUIRED` | Governed re-auth on `POST /api/billing/portal` and `POST /api/billing/checkout` when `X-Step-Up-Token` absent (expected; SPA modal handles this) |
| Stripe mode containment | `409` `STRIPE_CUSTOMER_MODE_DRIFT` / `MODE_UNVERIFIED` | Portal preflight (`validate_portal_billing_preflight`) blocks Billing Portal for legacy `MODE_UNVERIFIED` rows while **checkout already routes to deployment Checkout** |
| UX gap | Stripe never opens from “Update payment method” | Portal endpoint returned `409` with no checkout fallback; frontend only followed `portal_url` |

**Not root cause:** global route guard, Runtime Contract capability matrix, or archived/deleted leakage.

## State-by-state billing recovery matrix

See `BILLING_RECOVERY_STATE_MATRIX.json`.

Summary:

| State | portal_mode | Billing caps | Portal (after step-up) | Checkout (after step-up) |
|-------|-------------|--------------|------------------------|--------------------------|
| ACTIVE | FULL_ACCESS | ALLOW | portal_url | portal or checkout |
| CANCELLATION_SCHEDULED | FULL_ACCESS | ALLOW | portal_url | portal or checkout |
| CANCELLED_IMMEDIATE | BILLING_RECOVERY | ALLOW | portal or checkout fallback | checkout_url |
| SUBSCRIPTION_EXPIRED | BILLING_RECOVERY | ALLOW | portal or checkout fallback | checkout_url |
| SUSPENDED | SUSPENDED | ALLOW | portal or checkout fallback | checkout_url |
| READ_ONLY | READ_ONLY | ALLOW | portal or checkout fallback | checkout_url |
| ARCHIVED | ARCHIVED | DENY | 403 capability_denied | 403 capability_denied |
| ACCOUNT_DELETED | ACCOUNT_DELETED | DENY | 403 capability_denied | 403 capability_denied |

## Fix applied

### Backend

1. **`services/billing_recovery_authorization.py`** — governed helper `billing_recovery_write_allowed()` (requires `CAP_BILLING_CHECKOUT` write + non-terminal lifecycle).
2. **`services/stripe_service.create_billing_portal_session()`** — portal creation with governed fallback to deployment Checkout when portal preflight fails with `MODE_UNVERIFIED` / related drift actions.
3. **`routes/billing.py`** — portal route delegates to service; missing `stripe_customer_id` routes to recovery checkout when authorized.
4. **`stripe_mode_containment_service`** — `PORTAL_DRIFT_RECOVERY_FALLBACK_ACTIONS` + `fallback: checkout` in customer drift detail.

### Frontend

**`BillingPage.js` `openBillingPortal`** — follows `checkout_url` from portal response; on `409` with `fallback: checkout`, retries via `POST /billing/checkout` with current plan.

No global auth loosening. No Runtime Contract bypass. No account-specific hardcoding.

## Route trace evidence (staging, with step-up)

See `STAGING_API_PROBE_WITH_STEP_UP.json`.

Pre-fix staging (2026-07-08):

- **lere@yopmail.com** (`SUSPENDED`): caps all `ALLOW`; portal `409 MODE_UNVERIFIED`; checkout `200` with Stripe test checkout URL.
- **allison@yopmail.com** (`CANCELLATION_SCHEDULED`): caps all `ALLOW`; portal/checkout require step-up (same pattern).

Without step-up token both routes correctly return `403 STEP_UP_REQUIRED` (not capability denial).

## Tests run

### Backend (targeted)

```
tests/test_p0_billing_recovery_portal_authorization_01.py
tests/test_account_capability_enforcement_billing_client.py::TestBillingRecoveryNotBlocked
tests/test_billing_recovery_operations.py::test_create_upgrade_session_mode_unverified_uses_deployment_checkout
tests/test_step_up_sensitive_routes.py
```

**Result:** 60 passed

### Frontend (targeted)

```
BillingPage.capability.test.js
billingCapabilityAccess.test.js
ilp4Closeout.lifecycleJourney.test.js
```

**Result:** 28 passed

## Staging browser validation

Prior browser E2E (`p0_subscription_lifecycle_deployment_convergence_02`) confirmed recovery UX, CTAs, and no CAP leaks. Stripe did not open because headless flow did not complete step-up modal and portal returned `409` without fallback.

**Post-fix validation requires:**

1. Deploy backend (Render staging) with portal checkout fallback.
2. Deploy frontend (Vercel staging project `pleerity-enterprise-9jjg`) with `checkout_url` handling.
3. Re-run: lere (SUSPENDED), allison (CANCELLATION_SCHEDULED), one ACTIVE Professional account.
4. Confirm: step-up modal → Stripe opens → payment/webhook → `ACTIVE` / `FULL_ACCESS` where applicable.

## Remaining Stripe / test-account limitations

- **MODE_UNVERIFIED** legacy billing rows cannot use Billing Portal until mode is authoritatively verified; governed path is **deployment Checkout** (by design).
- **lere@yopmail.com** is org `SUSPENDED` (not `CANCELLED_IMMEDIATE`); use checkout/portal recovery, not cancel-immediate semantics.
- Full webhook → ACTIVE convergence E2E depends on Stripe test payment completion and Render webhook delivery.
- Step-up remains required for billing mutations (password re-confirmation); this is intentional security policy, not an authorization defect.

## Files changed

- `backend/services/billing_recovery_authorization.py` (new)
- `backend/services/stripe_service.py`
- `backend/routes/billing.py`
- `backend/services/stripe_mode_containment_service.py`
- `backend/tests/test_p0_billing_recovery_portal_authorization_01.py` (new)
- `frontend/src/pages/BillingPage.js`
- `frontend/src/pages/BillingPage.capability.test.js`
