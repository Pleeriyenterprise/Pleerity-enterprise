# Pending Payment Recovery (Compliance Vault Pro)

This document describes the Pending Payment Recovery feature: lifecycle tracking for unpaid clients, recovery endpoints, Stripe mode safety, lifecycle job, and operator workflows.

## Purpose

Clients who complete intake but do not pay remain in a pending state. Recovery allows operators to:

- List and search unpaid clients
- Send payment links (Stripe Checkout) to recover payments
- Track lifecycle (pending → abandoned → archived) without provisioning or entitlement changes

## Non-Negotiable Rules

1. **Provisioning only via Stripe webhooks** — Recovery never triggers provisioning.
2. **No entitlement grants at intake or when generating payment links** — Entitlements are granted only after successful payment (webhook).
3. **No deletion of unpaid clients** — Lifecycle job only updates `lifecycle_status`; no soft/hard delete.
4. **Stripe mode safety** — `sk_test_` keys must use TEST env vars only; `sk_live_` must use LIVE env vars only. Mismatch returns 400 `STRIPE_MODE_MISMATCH`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/intake/pending-payments` | List clients pending payment. Optional `q` for search (CRN, email, full_name, case-insensitive). |
| POST | `/api/admin/intake/{client_id}/send-payment-link` | Create Stripe checkout session; optionally email link. Idempotent within 30 min. |

## GET pending-payments Response Fields

Each item includes:

- `client_id`, `customer_reference`, `email`, `full_name`, `billing_plan`, `created_at`
- `lifecycle_status` (pending_payment | abandoned | archived)
- `subscription_status`, `onboarding_status`
- `latest_checkout_url`, `checkout_link_sent_at`
- `last_checkout_error` (object: `{ code, message, occurred_at }`) and flat `last_checkout_error_code`, `last_checkout_error_message`, `last_checkout_attempt_at`

## Lifecycle Job

The job `run_pending_payment_lifecycle` (in `backend/job_runner.py`) runs periodically:

- **14 days** after `checkout_link_sent_at` (or `created_at` if never sent): `pending_payment` → `abandoned`
- **90 days** after transition to abandoned: `abandoned` → `archived`

The job only updates `lifecycle_status`. It does not delete clients or change subscription/onboarding status.

## Operator Workflows

### From Pending Payments Page (`/admin/pending-payments`)

1. Use the search box to filter by CRN, email, or name.
2. For each client: click **Send link** to create a checkout session and optionally email the link.
3. Use **Copy link** to share the payment URL manually if email is not configured.
4. Columns **Name** and **Last link sent** help prioritise follow-ups.

### From Client Modal (Admin Dashboard)

1. Open a client and go to the **Setup** tab.
2. If "Stripe Payment Active" is not complete: **Send Payment Link** or **Resend Payment Link** appears.
3. After sending: "Last sent: {datetime}" and **Copy link** are shown.
4. The button is hidden once payment is complete (subscription active).

## Stripe Mode Safety

- TEST mode (`sk_test_*`): Only `STRIPE_TEST_PRICE_*` env vars may be used.
- LIVE mode (`sk_live_*`): Only `STRIPE_LIVE_PRICE_*` env vars may be used.
- Mismatch (e.g. live key with test price): Returns 400 with `error_code: STRIPE_MODE_MISMATCH`. The client record is updated with `last_checkout_error_code` and `last_checkout_error_message` for visibility.

## Data Model Additions

On `clients`:

- `lifecycle_status`: `pending_payment` | `abandoned` | `archived`
- `latest_checkout_session_id`, `latest_checkout_url`, `checkout_link_sent_at`
- `last_checkout_error_code`, `last_checkout_error_message`, `last_checkout_attempt_at`
