# BILLING-CLIENT-REMEDIATION-DIAGNOSTIC-01 — REPORT

Generated: 2026-06-03T07:11:20.158385+00:00

## Classification

**STRIPE_MODE_DRIFT**

## Client

- **client_id:** `80f83edd-ba12-41ed-929a-bbaf8c696a23`
- **probe account:** `nancy@yopmail.com` (Confidence Marcel / Solo Landlord staging)

## Root cause

Client self-serve plan changes call `create_upgrade_session` → `validate_portal_billing_preflight`, which blocks when `stripe_mode_verification_status` is `MODE_UNVERIFIED` (missing authoritative `stripe_mode` on `client_billing`).

Admin recovery **regenerate-checkout** was fixed to use deployment Checkout; **client `/billing/checkout` was not**, so refresh/regenerate attempts did not unblock the password-confirm upgrade UX.

## Safe remediation

1. **Code:** `requires_deployment_checkout_for_plan_change` shared helper; client checkout uses deployment Checkout when MODE_UNVERIFIED (same as recovery).
2. **Data (when authoritative):** `POST /admin/billing/stripe-mode-backfill` with `dry_run=false` when webhook/checkout evidence resolves live mode.

## Validation

- Checkout probe: `n/a`
- Portal probe: `n/a`

## Evidence

See `preflight_runtime.json`, `client_state_runtime.json`, `remediation_runtime.json`.
