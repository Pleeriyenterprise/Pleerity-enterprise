# BILLING-STRIPE-RUNTIME-FINGERPRINT-VERIFY-01

**Classification:** **VERIFIED_OPERATIONALLY**  
**Root cause (resolved):** **DUPLICATE_VALUES_CONFIRMED** → env corrected + redeployed

## 1. Deploy check

- `/api/version` commit: `579e20771649` (successor to `5f5613c2`)
- Redeploy after `STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY` correction: **confirmed**

## 2. Runtime fingerprint

| Plan | duplicate_group_id | last_6 |
|------|-------------------|--------|
| PLAN_1_SOLO | 66fe742a | djy27g |
| PLAN_2_PORTFOLIO | 1358f55e | hJv239 |
| PLAN_3_PRO | ab844bf9 | mumLiD |

- Three monthly vars distinct at runtime: **True**
- duplicate_detected: **False**
- load_error: **null**

## 3. Verification

### Read paths
- `/api/billing/plans`: 200
- `/api/client/entitlements`: 200
- `/api/billing/status`: 200

### Checkout HTTP
- Solo: HTTP 200 (`checkout_context: plan_change`)
- Portfolio: HTTP 200
- Professional: HTTP 200

### Stripe price display (Playwright hosted checkout)
- Solo: £19/month — **PASS**
- Portfolio: £39/month — **PASS**
- Professional: £79/month — **PASS**

### Cancel / back URLs (Playwright Stripe back button)
- All plans: cancel target `/settings/billing?checkout=cancelled` (via login `next` when unauthenticated session)
- **Not** `/intake/start` — **PASS**

## 4. Summary

Render env correction applied. Running process reads three distinct monthly price fingerprints. Billing checkout operational for all plans.

See `runtime_fingerprint_verify_01.json` and `checkout_stripe_verify_01.json`.
