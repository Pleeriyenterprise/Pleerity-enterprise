# Pilot Lifecycle Governance

Platform-governed pilot state complements Stripe billing. **Stripe** remains authoritative for subscriptions, invoices, and payments. **This service** governs pilot duration, extensions, cancellation, conversion, and comped access.

## Architecture

```
Invite / Checkout (Stripe)  →  webhook  →  pilot_lifecycle_service.create_from_invite_checkout
Admin actions               →  pilot_lifecycle_service.*  →  clients + pilot_lifecycle_audit
invoice.paid (amount > 0)   →  record_stripe_paid_transition  →  converted_to_paid
subscription.deleted        →  record_stripe_cancelled_before_paid (if applicable)
Feature access              →  entitlement_access (+ Stripe canonical state)
```

## Separated lifecycle domains (operational maturity)

`pilot_status` remains the admin mutation field. Reconciliation derives and persists:

| Field | Authority |
|-------|-----------|
| `pilot_governance_status` | Platform governance |
| `pilot_billing_status` | Stripe subscription / billing lifecycle |
| `pilot_entitlement_status` | Entitlement engine (`canonical_entitlement_state`) |

See [PILOT_OPERATIONAL_MATURITY.md](./PILOT_OPERATIONAL_MATURITY.md) for health scoring, anomalies, template governance, and ops playbooks.

## Lifecycle states (`pilot_status`)

| Status | Meaning |
|--------|---------|
| `active` | Pilot period in progress |
| `extended` | Admin extended beyond original `pilot_expires_at` |
| `expired` | Platform pilot period ended (Stripe may still bill if subscribed) |
| `converted_to_paid` | Pilot governance complete; paying or paid customer |
| `cancelled` | Pilot ended by admin or pre-paid Stripe cancel |
| `comped` | Strategic comp — platform grants access via governance |
| `paused` | Temporary admin pause |

## Client fields

Canonical fields on `clients` (see `pilot_lifecycle_service._snapshot_pilot_fields`). Legacy fields (`pilot_program_type`, `pilot_invite_code`, etc.) are kept in sync.

## Admin API

Base: `/api/admin/pilot-lifecycle` (requires `admin_route_guard`; mutations require step-up).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ops-dashboard?status=` | Ops summary + health + open anomalies |
| GET | `/accounts?status=` | List pilot accounts |
| GET | `/accounts/{client_id}` | Current state + effective expiry |
| GET | `/accounts/{client_id}/operational-profile` | Timeline, domains, health, anomalies |
| GET | `/accounts/{client_id}/history` | Audit trail |
| POST | `/accounts/{client_id}/reconcile` | Reconcile domains + health + anomalies |
| GET | `/anomalies` | Open operational anomalies |
| POST | `/anomalies/{anomaly_id}/resolve` | Resolve anomaly with notes |
| POST | `/accounts/{client_id}/create` | Admin override pilot on existing client |
| POST | `/accounts/{client_id}/extend` | Extend by days/weeks/months/until |
| POST | `/accounts/{client_id}/set-expiry` | Set absolute expiry |
| POST | `/accounts/{client_id}/cancel` | Cancel pilot; optional Stripe cancel |
| POST | `/accounts/{client_id}/convert-to-paid` | Mark converted (no reprovision) |
| POST | `/accounts/{client_id}/comp` | Comp account |
| POST | `/accounts/{client_id}/pause` | Pause |
| POST | `/accounts/{client_id}/resume` | Resume |
| PATCH | `/accounts/{client_id}/notes` | Update notes |
| POST | `/accounts/{client_id}/onboarding-fee-policy` | Override waive / defer / charge onboarding |

Invite code CRUD remains at `/api/admin/pilot-invites`.

### Onboarding fee admin override

`POST /api/admin/pilot-lifecycle/accounts/{client_id}/onboarding-fee-policy` (step-up required):

```json
{
  "reason": "Executive approval — waive setup fee",
  "onboarding_fee_policy": "waived",
  "waiver_reason": "Founding pilot cohort 2026"
}
```

Policies: `waived`, `deferred`, `charge_now`, `discount`. Optional `deferred_until`, `mark_charged` (records `onboarding_fee_charged_at` and sets `onboarding_fee_paid` on billing).

`GET /accounts/{client_id}` returns `onboarding_fee` summary alongside pilot state.

## Extension strategy

- **Platform:** `pilot_extended_until` and `pilot_expires_at`; effective expiry = max of both.
- **Stripe:** Repeating coupons are fixed at checkout. Admin extension does **not** mutate Stripe coupons by default (avoids invoice chaos).
- To end Stripe discount early: admin **convert to paid** + normal billing, or **cancel** with `cancel_stripe_subscription: true`.

## Comp accounts

- `pilot_status=comped` with audit reason (minimum 10 characters).
- **Owner role only** (`POST .../comp` uses `require_owner` + step-up).
- Persists `pilot_comped_by`, `pilot_comped_by_email`, optional `pilot_comp_review_expires_at`.
- Comped accounts bypass Stripe subscription checks in `entitlement_access` — use only for strategic exceptions.

## Conversion observability

Client fields (set by Stripe webhooks / lifecycle):

| Field | Meaning |
|-------|---------|
| `pilot_converted_to_paid_at` / `pilot_transitioned_to_paid_at` | First paid conversion |
| `pilot_first_paid_invoice_id` / `pilot_first_paid_invoice_at` | First non-zero invoice |
| `pilot_first_paid_invoice_paid` | Boolean |
| `pilot_cancelled_before_paid_conversion` | Cancelled before paid |
| `pilot_conversion_failure` | e.g. `cancelled_before_paid` |
| `pilot_stripe_payment_method_collected` | PM on file (sync via admin or post-checkout webhook) |

## Ops dashboard

`GET /api/admin/pilot-lifecycle/ops-dashboard` — pilot status, expiry, onboarding policy, conversion flags, PM collected, invite code, days remaining.

`POST /api/admin/pilot-lifecycle/accounts/{id}/sync-stripe-payment-method` — refresh PM status from Stripe.

## Deferred onboarding policy

`onboarding_fee_policy=deferred` is **experimental**: blocked on invite create/update and public checkout. Not automated for post-pilot charging.

## Comp accounts (legacy note)

- `pilot_status=comped` with audit reason.
- `evaluate_subscription_feature_access` allows access when comped (even if Stripe subscription is weak/absent).
- Do not use comp for routine pilots — use invite + repeating coupon.

## Enforcement

- `pilot_governance_revoke_access=true` on cancel with `revoke_access_immediately` blocks API features (except comped).
- `paused` blocks access until resumed.
- **Expired** pilot does not block if Stripe subscription is still active.

## Audit

Collection: `pilot_lifecycle_audit` (append-only, idempotent keys for webhooks).

## Frontend gap

No admin UI for pilot lifecycle yet. Use API or ops tooling. Intake UI shows invite validation only.

## Rollback

- Disable invite codes to stop new pilots.
- Admin cancel / convert individual accounts.
- Code rollback preserves Mongo pilot fields; Stripe subscriptions unchanged.

## Related docs

- `PILOT_INVITE_STRIPE_CHECKOUT.md` — Stripe coupon setup and checkout flow
