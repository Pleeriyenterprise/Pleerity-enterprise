# Action Matrix — Admin Lifecycle Operations

**Programme:** ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01  

Core principle: admins execute **governed operations**, never manual lifecycle truth overrides.

---

## Read operations (no mutation)

| Admin need | API / UI | Authority source |
|------------|----------|------------------|
| Lifecycle state, portal mode, reason | `GET .../lifecycle-operations` → `lifecycle` | Runtime Contract resolver |
| Transition / runtime version | same → `lifecycle.runtime_version` | Runtime Contract |
| Capability summary | same → `capabilities` | Capability matrix from contract |
| Billing mirror | same → `billing` (labeled mirror) | `client_billing` |
| Stripe IDs, sync state, drift | same → `billing` | Mirror + reconciliation flags |
| Webhook events | same → `stripe_webhooks` | `stripe_events` + billing pointers |
| Action eligibility | same → `actions` | Derived server-side |
| Audit timeline | same → `lifecycle_audit_timeline` | `audit_logs` |

---

## Write operations (governed)

| # | Action | UI | API | Backend authority | Idempotent | Step-up |
|---|--------|-----|-----|-------------------|------------|---------|
| 1 | Run billing reconciliation from Stripe | Reconcile from Stripe | `POST .../reconcile-stripe` | `sync_client_billing_from_stripe_subscription_id` + `sync_subscription_lifecycle` | Safe to retry (Stripe read + sync) | No |
| 2 | Refresh Runtime Contract | Refresh Runtime Contract | `POST .../refresh-runtime-contract` | `invalidate_runtime_cache_for_client` + `resolve_runtime_contract_for_client` | Yes | No |
| 3 | Generate/send recovery checkout | Link to Billing → Recovery | Billing Centre (existing) | Billing recovery services | N/A | Per existing policy |
| 4 | Resume scheduled cancellation | Resume scheduled cancellation | `POST .../resume-subscription` | `stripe_service.resume_subscription` | Stripe-governed | **Yes** |
| 5 | Replay Stripe webhook | Blocked in UI | Not exposed | — | — | — |
| 6 | Mark for support review | Flag for billing support review | `POST .../mark-support-review` | Audit log only | Yes | No |
| 7 | View lifecycle audit timeline | Panel section | `GET` snapshot | Read-only | — | — |
| 8 | View event processing status | Stripe & webhooks section | `GET` snapshot | Read-only | — | — |
| 9 | View capability matrix | Capability summary in snapshot | `GET` snapshot | Read-only | — | — |

---

## Blocked / unsafe patterns (must not exist)

| Bad pattern | Status |
|-------------|--------|
| `Set user to ACTIVE` | **Not implemented** |
| Direct `lifecycle_state` PATCH | **Not implemented** |
| Bypass Stripe for billing truth | **Not implemented** |
| Ungoverned webhook replay | **Not implemented** (use reconcile) |

---

## Eligibility rules (server-derived)

| Action | Available when | Blocked reason examples |
|--------|----------------|-------------------------|
| Reconcile from Stripe | Stripe customer or subscription on record | No Stripe customer or subscription |
| Refresh runtime | Always | — |
| Resume cancellation | Sub exists, `cancel_at_period_end`, not terminal canceled | Not scheduled; already canceled |
| Recovery checkout link | Recovery state or deployment checkout required | Account not in recovery state |
| Mark support review | Always | — |
| Replay webhook | Never (in this programme) | Use reconcile from Stripe |

---

## Audit metadata

| Action | `action_type` |
|--------|---------------|
| Refresh runtime | `LIFECYCLE_OPS_REFRESH_RUNTIME` |
| Reconcile Stripe | `LIFECYCLE_OPS_RECONCILE_STRIPE` |
| Resume subscription | `LIFECYCLE_OPS_RESUME_SUBSCRIPTION` |
| Support review flag | `LIFECYCLE_OPS_SUPPORT_REVIEW_FLAGGED` |
