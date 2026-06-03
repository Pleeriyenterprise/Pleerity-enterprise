# BILLING-PLAN-CHANGE-CHECKOUT-ROUTING-BUG-01

**Classification:** **VERIFIED_OPERATIONALLY**

## Root cause

Deployment plan-change reused onboarding `create_checkout_session` URLs (`/checkout/cancel` → `/intake/start`). Portfolio-every-time can also occur when Stripe price env vars map multiple plans to the same price id.

## Fix

- `checkout_context` separates onboarding vs plan-change vs recovery plan-change
- Billing return URLs: `/settings/billing?checkout=success|cancelled`
- Duplicate price-id validation + session line-item verification
- BillingPage toast on return from Stripe

## Tests

`test_plan_change_checkout_routing.py` + existing containment/recovery suites.
