# Founding Pilot — Live Stripe Checkout with Invite Codes

Founding pilot users complete the **real live Stripe Checkout** flow (subscription line item only when onboarding is waived). Authorised invite codes apply discounts via **pre-created Stripe coupons** (or promotion codes) stored on each invite record. Provisioning and entitlements remain driven by **Stripe webhooks**, not the checkout API.

**Default founding pilot billing:** 100% off subscription for **2 months** (repeating Stripe coupon) + **onboarding/setup fee waived** (`onboarding_fee_policy=waived`). After the pilot, Stripe charges **subscription only** — waived onboarding is never re-added by checkout or webhooks unless an admin overrides policy.

## Discount models

| Mode | Stripe coupon | Platform behaviour |
|------|---------------|-------------------|
| **Repeating** (default for new invites) | `percent_off=100`, `duration=repeating`, `duration_in_months=2` | £0 invoices for pilot months; Stripe bills full price afterward; PM collected at checkout (`always`) |
| **Forever** | `duration=forever`, 100% off | Legacy / special cases; PM `if_required` when checkout total is £0 |
| **Once** | `duration=once` | Single invoice discount only |

The invite record stores `discount_type`, `discount_percent`, `discount_duration`, `discount_duration_in_months` for tagging, UX, and admin visibility. **Stripe coupon settings must match** these fields (the app does not create coupons per checkout).

## Flow

1. User enters optional invite code on intake Step 5 (`POST /api/intake/pilot-invite/validate`).
2. Step 5 agreement preview (`POST /api/intake/agreement-preview`) must render with the same pilot commercial truth before payment can proceed.
3. Agreement acceptance (`POST /api/public/agreements/acceptance`) carries the invite context so the accepted agreement snapshot matches checkout.
4. `POST /api/intake/checkout` accepts optional `invite_code` with `acceptance_id`.
5. `stripe_service.create_checkout_session` creates a normal subscription Checkout Session with:
   - `discounts: [{ coupon: ... }]` or `[{ promotion_code: ... }]`
   - `payment_method_collection: always` when `discount_duration=repeating` (card on file for post-pilot billing)
   - `payment_method_collection: if_required` for forever/once 100% off when checkout total is £0
   - Metadata: `program_type`, `invite_code`, `pilot_discount_months`, `pilot_duration_months`, `expected_transition_to_paid`, `selected_plan_code`, `onboarding_fee_policy`, `onboarding_fee_waived`, etc.
   - **No onboarding line item** when `onboarding_fee_policy=waived` or `deferred`
6. `checkout.session.completed` webhook tags the client, registers a **pending** redemption.
7. After provisioning completes (`provisioning_runner` → `PROVISIONING_COMPLETED`), `used_count` increments **once** (idempotent on `checkout_session_id`).
8. During pilot: `invoice.paid` with `amount_paid=0` still runs normal handlers (entitlements follow subscription status).
9. First **non-zero** `invoice.paid` sets `pilot_transitioned_to_paid_at` (no reprovisioning).
10. `customer.subscription.deleted` before paid conversion sets `pilot_cancelled_before_paid_conversion`.

## Stripe Dashboard setup — 100% off for 2 months (live)

### Create the coupon

1. Stripe Dashboard → **Product catalogue** → **Coupons** → **Create coupon**.
2. **Type**: Percentage discount → **100%**.
3. **Duration**: **Repeating** → **2 months** (must match invite `discount_duration_in_months`).
4. **Applies to**: All products, or restrict to CVP subscription/onboarding prices if you use product restrictions.
5. Copy the **Coupon ID** (e.g. `FOUNDING_PILOT_100_2MO_LIVE`).

### Optional promotion code

1. On the coupon → **Promotion codes** → create customer-facing code (e.g. `FOUNDING2026`).
2. Copy the **Promotion code ID** (`promo_...`) if using `discount_mode: promotion_code`.

### Payment method collection

- Checkout uses `payment_method_collection: always` for repeating pilots so Stripe can charge after month 2.
- Customer may still see £0 due today; card is saved for future cycles.
- **Limitation**: If Stripe account/settings block PM collection for £0 checkout in your mode, test in live mode with a real invite; adjust only if Stripe returns an error (do not bypass Stripe).

### Onboarding (setup) fee

- Repeating 100% coupons typically discount **subscription line items** for 2 billing periods; setup fee may be charged on first invoice depending on coupon scope. Verify in Stripe test/live with your price IDs.

## App configuration — invite codes

### Admin UI

Navigate to **Products & Billing → Founding Pilot Invites** (`/admin/pilot-invites`).

- Create invites with Stripe coupon validation before save
- Copy invite URL / message (commercial wording from `pilot_commercial_truth`)
- View usage, linked accounts, and deactivate invites
- Distribution URL pattern: `/intake/start?invite=CODE&plan=PLAN_1_SOLO`

### Admin API (owner/admin RBAC)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/admin/pilot-invites/operational-config` | Safe Stripe/env checklist (no secrets); see `STRIPE_MODE_GOVERNANCE.md` |
| GET | `/api/admin/pilot-invites` | List codes (filters: status, policy, duration, plan) |
| GET | `/api/admin/pilot-invites/suggest-code` | Generate invite code suggestion |
| POST | `/api/admin/pilot-invites/validate-stripe` | Validate coupon vs invite fields (no persist) |
| POST | `/api/admin/pilot-invites` | Create code |
| GET | `/api/admin/pilot-invites/{code}` | Invite detail |
| PATCH | `/api/admin/pilot-invites/{code}` | Update max uses, notes, expiry, Stripe IDs |
| PATCH | `/api/admin/pilot-invites/{code}/disable` | Disable code |
| GET | `/api/admin/pilot-invites/{code}/usage` | Redemptions + accounts |
| GET | `/api/admin/pilot-invites/{code}/distribution` | Share URL + message template |
| GET | `/api/admin/pilot-invites/accounts` | Pilot clients + lifecycle fields |

Example create body (2-month founding pilot):

```json
{
  "code": "FOUNDING-2026-A",
  "program_type": "FOUNDING_PILOT",
  "applies_to_plan_codes": ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO"],
  "max_uses": 10,
  "stripe_coupon_id": "FOUNDING_PILOT_100_2MO_LIVE",
  "discount_mode": "coupon",
  "discount_type": "percent",
  "discount_percent": 100,
  "discount_duration": "repeating",
  "discount_duration_in_months": 2,
  "waive_onboarding_fee": true,
  "onboarding_fee_policy": "waived"
}
```

## Client lifecycle fields

| Field | Meaning |
|-------|---------|
| `pilot_program_type` | e.g. `FOUNDING_PILOT` |
| `pilot_invite_code` | Normalised invite code |
| `pilot_started_at` | Webhook checkout completion |
| `pilot_discount_applied` | true |
| `pilot_discount_percent` | e.g. 100 |
| `pilot_discount_months` | e.g. 2 |
| `pilot_discount_duration` | `repeating` / `forever` / `once` |
| `pilot_expected_first_paid_invoice_at` | Estimated calendar date (start + months) |
| `pilot_expected_transition_to_paid` | true for repeating pilots |
| `pilot_transitioned_to_paid_at` | Set on first `invoice.paid` with `amount_paid > 0` |
| `pilot_cancelled_before_paid_conversion` | Set on subscription deleted before transition |
| `onboarding_fee_policy` | `waived` / `deferred` / `charge_now` / `discount` |
| `onboarding_fee_waived` | true when permanently waived |
| `onboarding_fee_waived_at` / `_by` / `_waiver_reason` | Audit trail |
| `onboarding_fee_deferred_until` | When policy is `deferred` |
| `onboarding_fee_charged_at` | When collected (checkout or admin `mark_charged`) |
| `onboarding_fee_amount` / `onboarding_fee_currency` | Plan snapshot (minor units / ISO) |

Nested `pilot` object mirrors key fields for support tooling.

## £0 invoices / webhooks

- `checkout.session.completed` fires for subscription checkout with discounts.
- `invoice.paid` / `invoice.payment_succeeded` fire for £0 invoices (`amount_paid=0`); provisioning and entitlements use **subscription status**, not invoice amount.
- `payment_intent` may be absent on £0 invoices; existing handlers must not require PI for subscription renewals.
- After discount ends, Stripe generates invoices at list price; failed payment uses existing dunning / `invoice.payment_failed` paths.

## Commercial truth consistency

All customer-facing commercial surfaces should reflect the same pilot terms via `services/pilot_commercial_truth.py`:

| Surface | Behaviour |
|---------|-----------|
| Agreement preview / acceptance snapshot | `onboarding_fee_minor=0` when waived; `pilot_commercial_summary` in snapshot |
| Intake `/plans` + payment summary | Pilot-adjusted setup fee and total when invite validated |
| Stripe checkout metadata | `onboarding_fee_policy`, `onboarding_fee_waived` |
| Payment confirmation email | `pilot_offer_line` + pilot-aware `amount_display` |
| Admin ops dashboard | `GET /api/admin/pilot-lifecycle/ops-dashboard` |

If a user applies a pilot invite **after** agreement acceptance, they must re-accept (checkout validates commercial snapshot with invite at payment time).

## Agreement preview dependencies

Step 5 is a payment gate. `Proceed to Payment` remains disabled until the agreement preview loads, renders without unresolved placeholders, and the user accepts it.

Agreement rendering depends on:

- `agreement_seed.py` publishing an active template with `{{monthly_fee}}`, `{{onboarding_fee_line}}`, and `{{pilot_offer_line}}`.
- `agreement_commercial_snapshot.py` carrying `billing_amount_minor`, `recurring_monthly_minor`, `first_checkout_total_minor`, onboarding fee status, pilot discount percent/months, and `pilot_commercial_summary`.
- `pilot_commercial_truth.py` owning onboarding fee and pilot summary wording. The onboarding fee helper contract is `build_onboarding_fee_line(ctx, onboarding_minor=0)`.
- `routes/intake.py` returning structured preview errors with `error_code` and `request_id`; raw exceptions must stay in backend logs only.

For the default founding pilot (`100%` off for `2` months, onboarding waived, `PLAN_1_SOLO`), the agreement must show:

- `One-time onboarding fee: Waived (Founding Pilot)`
- `Your first 2 months are free.`
- `After the pilot, your subscription continues at £19.00/month unless cancelled before renewal.`
- recurring subscription wording from the plan-and-fees block

## Stripe coupon validation (admin create/update)

`POST /api/admin/pilot-invites` validates the configured Stripe coupon/promotion via API:

- Coupon exists and is valid
- `percent_off` matches invite `discount_percent`
- `duration` / `duration_in_months` match invite record

Misconfigured invites are rejected before operational use.

## Pilot lifecycle reconciliation worker

Scheduled job `pilot_lifecycle_reconcile` (hourly, UTC minute 25):

- Scans `pilot_status` in `active` / `extended`
- Calls `sync_expired_if_due` (idempotent audit per client/date)
- Does **not** mutate Stripe subscriptions

## Operational guidance

- **Converting pilots to paying customers**: No manual job — ensure Stripe coupon is repeating (not forever), PM collected at checkout, and customer does not cancel before month 3.
- **Support**: Use admin `GET /api/admin/pilot-invites/accounts` for transition state.
- **Admin UI**: Not implemented; use API or ops scripts.

## Rollback

1. Disable invite codes (stops new checkouts).
2. Do not delete Stripe coupons attached to active subscriptions.
3. Code rollback does not cancel existing Stripe subscriptions.

## Tests

- `backend/tests/test_pilot_invite_checkout.py` — invite validation, checkout wiring, metadata, paid transition idempotency
- `backend/tests/test_pilot_onboarding_fee.py` — onboarding policy resolution, webhook waived logic, admin override
