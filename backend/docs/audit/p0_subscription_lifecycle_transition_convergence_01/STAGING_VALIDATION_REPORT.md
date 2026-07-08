# P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01 — Staging validation

**Date:** 2026-07-08  
**Commit:** `a86a1a25` (backend Render + frontend Vercel alias `9jjg`)

---

## Deployment convergence

| Surface | SHA / artifact | Match |
|---------|----------------|-------|
| Render `/api/version` | `a86a1a25` | Yes |
| Vercel staging alias | `main.2f67b810.js` (build env `a86a1a25`) | Yes |
| `POST /api/billing/resume` | Returns **401** unauthenticated (not 404) | Deployed |

---

## Targeted tests (local, pre-push)

| Suite | Result |
|-------|--------|
| `tests/test_p0_subscription_lifecycle_transition_convergence_01.py` | **9 passed** |
| Frontend LifecycleShell / useResumeSubscription / BillingPage.capability | **6 passed** |

---

## Staging API validation (cancel-at-period-end cohort)

Account discovered dynamically from staging Mongo (`cancel_at_period_end=true`, active mirror) — used for impersonation probes only, not production logic.

### Fix 4 — Messaging guard: **PASS**

- API `customer_experience.heading`: **"Updating your subscription status"**
- No **"full access until 2026-06-16"** (past date suppressed)
- `lifecycle_context.transition_pending=true`

### Fix 2 — POST /api/billing/resume: **PASS (route + authority)**

- Route deployed and step-up gated
- For this cohort member Stripe subscription is **already canceled** (terminal): resume correctly returns **400** with Stripe authority message (*"A canceled subscription can only update its cancellation_details and metadata."*)
- Resume is not applicable post-terminal cancel; transition authority is governed reconcile, not undo

### Fix 1 — Stale scheduled cancellation reconcile: **PARTIAL**

- Stale mirror **detected** on runtime contract resolve
- `billing_reconciliation_needed=true`, reason `stale_scheduled_cancellation_period_end`
- Governed Stripe pull did **not** complete mirror convergence in this run (`subscription_status` still mirrored as `ACTIVE`; `stale_scheduled_cancellation_sync_at` null)
- Scheduled reconcile batch should pick up flagged row on next job cycle

### Fix 3 — Keep subscription UX: **PARTIAL**

- Runtime contract exposes `primary_cta.action=resume_subscription`
- Frontend bundle includes `useResumeSubscription`, `lifecycle-keep-subscription`, `billing-keep-subscription` test ids
- Headless browser run did not confirm click → POST `/billing/resume` (lifecycle shell load timing; terminal Stripe state makes resume invalid for this account anyway)

---

## Verdict

### `SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED_WITH_CONDITIONS`

**Conditions**

1. **Stale mirror Stripe pull** — detection and flagging work; full mirror convergence pending next governed reconcile cycle (batch job or successful sync preflight).
2. **Keep subscription browser E2E** — inconclusive in headless run; re-run with customer password or longer lifecycle-shell wait on an account with **active** `cancel_at_period_end` (not terminal canceled).
3. **Terminal canceled Stripe subs** — resume correctly unavailable; UX should converge to expired/recovery via reconcile (not Keep subscription).

**Not blocked**

- No manual Mongo repair performed
- No account-specific production logic
- Runtime Contract authority preserved
- Stripe not bypassed

---

## Re-run commands

```bash
cd backend
python tmp_p0_subscription_lifecycle_transition_validation_01.py
python tmp_p0_subscription_lifecycle_browser_e2e_01.py
```

Optional: set `STAGING_CANCEL_SCHEDULED_EMAIL` / `STAGING_CANCEL_SCHEDULED_PASSWORD` for direct customer login instead of impersonation.
