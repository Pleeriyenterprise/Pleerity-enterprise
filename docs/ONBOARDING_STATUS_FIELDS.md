# Onboarding Status Fields

## GET /api/onboarding/status

Used by the post-payment onboarding progress screen for polling. Reads from DB only; no Stripe calls.

### Response Fields

| Field | Source | Description |
|-------|--------|-------------|
| `customer_reference` | `clients.customer_reference` | CRN (e.g. PLE-CVP-2026-000001) |
| `payment_status` | Derived from `clients.subscription_status` | `"paid"` when ACTIVE/PAID/TRIALING; else `"pending"` |
| `subscription_status` | `clients.subscription_status` | Set by Stripe webhook when payment succeeds |
| `provisioning_status` | `clients.onboarding_status` | PROVISIONED / PROVISIONING / FAILED / INTAKE_PENDING |
| `portal_user_exists` | `portal_users` collection | True when a portal user record exists (created by webhook-triggered provisioning) |
| `password_set` | `portal_users.password_status` | True when user has set password |
| `created_at` | `clients.created_at` | Used for "Confirming…" display (recent Stripe redirect) |
| `updated_at` | `clients.updated_at` | Last update timestamp |

### Payment / Provisioning State Determination

- **Payment:** `subscription_status` is set by the Stripe `checkout.session.completed` webhook. Only webhooks update this; the UI never triggers provisioning.
- **Provisioning:** `onboarding_status` moves to PROVISIONING → PROVISIONED via the provisioning job, which is triggered by the webhook (payment confirmed).
- **Portal user:** Created during provisioning. Until `portal_user_exists` is true, the "Set password" step remains disabled.
