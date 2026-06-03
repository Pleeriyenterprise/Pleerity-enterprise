# BILLING-PLAN-CHANGE-ROUTING-AND-CLIENT-PROOF-01

**Classification:** **PARTIAL**  
**Generated:** 2026-06-03

## Summary

Plan-change routing correctly separates **drift** (test-on-live / MODE_UNVERIFIED) from **healthy live** rows. Drift clients route to `deployment_checkout`; verified live/live rows route to Stripe Billing Portal `subscription_update_confirm`. Affected client `confidence@yaho.co.uk` cannot complete portal proof yet (no password; resend-setup blocked by Postmark inactive recipient).

## Routing rules (code audit)

| Scenario | `requires_deployment_checkout` | Path |
|----------|-------------------------------|------|
| A. Verified live on live deployment | false | Portal `subscription_update_confirm` |
| B. Stored test on live deployment | true | `deployment_checkout` |
| C. MODE_UNVERIFIED | true | `deployment_checkout` |
| D. No subscription/customer | true | New `create_checkout_session` |

All scenario matches: **pass** (`billing_routing_rules_runtime.json`).

## Affected drift client (`80f83edd…`)

- **Portal:** provisioned, entitlement ACTIVE, password **not set**
- **Resend-setup:** **502** — Postmark inactive recipient (`confidence@yaho.co.uk`)
- **Login:** 401 with ops probe password
- **Checkout (proxy cohort `nancy@yopmail.com`):** 200, `plan_change_path: deployment_checkout`, no refresh-block copy
- **Safety:** legacy subscription id unchanged; no duplicate subscription

## Live subscriber guardrail

- Staging sample: **no** `stored_stripe_mode=live` rows at probe time (including former live client Harrison — now `test`)
- **Unit test:** `test_create_upgrade_session_verified_live_uses_portal_not_deployment_checkout` — **pass**
- Confirms healthy live rows do **not** use `deployment_checkout`

## Admin recovery

- Guidance: `VERIFIED_OPERATIONALLY` (live checkout session evidence)
- Dashboard row may still show stale `MODE_UNVERIFIED` label
- Regenerate-checkout: **409** when case `RECOVERY_RESOLVED` (expected)

## Regression

40 tests passed (`test_stripe_mode_containment` + `test_billing_recovery_operations`).

## Verdict

**PARTIAL** — routing and drift path verified on staging + unit tests; affected customer portal access blocked pending deliverable password-setup email.
