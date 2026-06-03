# BILLING-PRICE-ID-RUNTIME-DUPLICATE-DIAGNOSTIC-01

**Classification:** **STRIPE_PRICE_CONFIG_DRIFT**

## Root cause (duplicate price)

Deployment fingerprint shows **duplicate_monthly_groups**: all three `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY` env vars resolve to the **same** price fingerprint (`duplicate_group_id` collision).

This is **DUPLICATE_RENDER_VALUES** — not a code resolution bug. Code reads only `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY` (no legacy fallback).

## Legacy drift (separate)

Client `6aa7906f-ed85-4367-8ca4-6ef1bb76668f` has test-mode subscription on live deployment (`sub_…` exists in test mode only). Logged as warning; separate from duplicate env issue.

## Remediation

1. Fix Render env: three distinct monthly price IDs.
2. Redeploy/restart backend.
3. Read paths degrade gracefully; checkout remains blocked until env fixed.

See `runtime_price_fingerprint.json` for masked group evidence.
