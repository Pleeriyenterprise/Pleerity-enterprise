# P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01 — Root cause (initial)

**Date:** 2026-07-08  
**Scope:** staging; lifecycle transition engine (not Stripe payment recovery)

---

## Executive summary

Two **independent, architectural** gaps explain the Allison observation. They are not related to the validated Stripe checkout recovery path.

| Defect | Layer | Global impact |
|--------|-------|---------------|
| **D-1** Stale `CANCELLATION_SCHEDULED` + `FULL_ACCESS` past period end | Background reconciliation + resolver fact authority | Any customer with missed terminal Stripe webhook |
| **D-2** “Keep subscription” appears inert | Frontend CTA + missing R-003 resume API | All `CANCELLATION_SCHEDULED` customers |

---

## Observed case: allison@yopmail.com

**Mongo mirror (read-only probe 2026-07-08T21:55Z):**

| Field | Value |
|-------|-------|
| `client_id` | `5db7bba1-ed9d-444e-9e0d-b7478d5b566b` |
| `subscription_status` | `ACTIVE` |
| `cancel_at_period_end` | `true` |
| `current_period_end` | **2026-06-16** (22 days before probe) |
| `billing_lifecycle_state` | `cancel_at_period_end` |
| `billing_sync_state` | `ok` |
| `billing_reconciliation_needed` | `false` |
| `stripe_webhook_last_received_at` | **2026-05-16** (`customer.subscription.updated`) |
| `billing_last_synced_at` | 2026-07-08 (recent portal/status read — mirror not refreshed from Stripe) |

**Runtime Contract (UI):** `CANCELLATION_SCHEDULED` / `FULL_ACCESS` — banner: “You have full access until 2026-06-16…”

This is **internally consistent with stored facts** but **customer-visible contradiction** because facts are stale relative to wall clock and Stripe truth.

---

## D-1 — Scheduled cancellation does not auto-converge after period end

### Authoritative design (correct while facts are fresh)

- Resolver: `ACTIVE` + `cancel_at_period_end` → `CANCELLATION_SCHEDULED` + `FULL_ACCESS`  
  (`account_lifecycle_state_resolver.py`)
- **No clock check** on `current_period_end` in resolver — by design trusts billing mirror.
- Terminal transition **T-011** authority: Stripe `customer.subscription.deleted` (or updated facts clearing access).

### Failure mode

1. Customer schedules cancel at period end.
2. Period ends; Stripe cancels subscription.
3. **Webhook missed** (or pre-webhook-config era) → Mongo still `ACTIVE` + `cancel_at_period_end=true`.
4. Resolver continues emitting `CANCELLATION_SCHEDULED` + `FULL_ACCESS`.
5. Banner shows expired access date while customer still has full access.

### Reconcile job gap

`stripe_subscription_reconcile_job.reconcile_all_stripe_subscriptions()` only selects rows where:

- `billing_reconciliation_needed == true`, OR
- `billing_sync_state != ok`

Allison has **`ok` + `false`** → **excluded** from scheduled reconcile despite `current_period_end` in the past.

### Missing global safety net

No worker scans: `cancel_at_period_end=true AND current_period_end < now` → force Stripe pull + lifecycle sync.

---

## D-2 — “Keep subscription” first failing layer

### Trace

```
Customer clicks "Keep subscription"
  → LifecycleShell CtaButton
  → <Link to="/settings/billing">   (navigation only)
  → BillingPage: informational cancel notice only
  → NO resume API
  → NO Stripe Subscription.modify(cancel_at_period_end=False)
```

### First authoritative failure

**Frontend UX + missing backend route** — not webhook, not resolver.

Governance **R-003** (`ACCOUNT_REACTIVATION_AUTHORITY.md`) documents “Resume subscription API” with billing validation `cancel_at_period_end: false`, but **no client route implements it** (`routes/billing.py` has cancel + portal only).

If customer is already on `/settings/billing`, click produces **no visible change** (same-route navigation).

---

## State machine authority (single source)

| Layer | Authority file |
|-------|------------------|
| Account lifecycle states | `services/account_lifecycle_state_resolver.py` |
| Billing lifecycle | `services/subscription_lifecycle_service.py` |
| Portal mode + banner + CTAs | `services/account_lifecycle_runtime_contract.py` |
| Transitions (events) | `services/account_lifecycle_event_authority.py` |
| Stripe writes | `services/stripe_service.py`, `services/stripe_webhook_service.py` |
| Scheduled repair | `services/stripe_subscription_reconcile_job.py`, `services/jobs.py` |

No competing lifecycle authority detected — **convergence failure is fact staleness + missing resume path**, not dual state machines.

---

## Remediation direction (global, architectural)

### Fix 1 — Time-based billing fact reconciliation (D-1)

Extend scheduled reconcile (or dedicated lifecycle transition scan) to include **any** subscription where:

- `cancel_at_period_end == true` AND `current_period_end < now`, OR
- `subscription_status` in terminal Stripe states but resolver still in pre-terminal band, OR
- `billing_last_synced_at` older than threshold while period boundary passed

Action: `sync_client_billing_from_stripe_subscription_id` → `sync_subscription_lifecycle` → runtime contract bump.

Must be **idempotent**, **audited**, and apply to **all clients** — not Allison-only.

### Fix 2 — R-003 Resume subscription (D-2)

1. **Backend:** `POST /api/billing/resume` (step-up gated) → Stripe `Subscription.modify(cancel_at_period_end=False)` → sync lifecycle → webhook confirmation.
2. **Frontend:** Wire “Keep subscription” to resume action (or portal with explicit undo intent), not same-page link.
3. **BillingPage:** Prominent undo control when `CANCELLATION_SCHEDULED`.
4. **Messaging:** After period end, banner must not show future/past access date — resolver-driven copy for post-expiry states.

### Fix 3 — Customer messaging guard

When `current_period_end < now` and still `CANCELLATION_SCHEDULED`, treat as **reconciliation-required** state in runtime contract (interim copy + trigger background sync), never show stale date as authoritative.

---

## Validation programme (next)

1. Confirm Stripe truth for Allison (`sub_1TMnwjCF0O5oqdUz2FQoLUfX`) — canceled vs still active.
2. Implement Fix 1 + Fix 2 (after approval).
3. Deploy staging; verify Allison converges without Mongo manual edit.
4. Browser E2E: cancel at period end → keep subscription → cancel → period expiry (simulated via Stripe test clock or governed test account).
5. Regression matrix: Solo / Portfolio / Professional × cancel paths.
6. Evidence pack: `LIFECYCLE_STATE_MATRIX.json`, `TRANSITION_VALIDATION.json`, browser screenshots.

---

## Verdict (initial)

**`SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGENCE_BLOCKED`**

First failures: **scheduled period-end fact reconciliation (D-1)**, **R-003 resume path missing (D-2)**.
