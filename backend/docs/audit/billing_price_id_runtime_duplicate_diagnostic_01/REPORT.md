# BILLING-STRIPE-RUNTIME-FINGERPRINT-VERIFY-01

**Classification:** **STRIPE_PRICE_CONFIG_DRIFT**  
**Root cause:** **DUPLICATE_VALUES_CONFIRMED**

## 1. Deploy check

- `/api/version` commit: `5f5613c25b0c` (min `5f5613c2`)
- Pass: **True**

## 2. Runtime fingerprint

Admin `GET /api/admin/billing/stripe-price-env-fingerprint` (masked):

| Plan | duplicate_group_id | last_6 |
|------|-------------------|--------|
| PLAN_1_SOLO | 66fe742a | djy27g |
| PLAN_2_PORTFOLIO | 1358f55e | hJv239 |
| PLAN_3_PRO | 1358f55e | hJv239 |

- Three monthly vars distinct at runtime: **False**
- duplicate_detected: **True**

## 3. Mode / env source

- STRIPE_MODE runtime: **live**
- Secret key: `STRIPE_SECRET_KEY_LIVE` (live) with legacy fallback only if unset
- Service: **pleerity-enterprise.onrender.com** → **pleerityenterprise.co.uk**

## 4. Price resolution

Direct `os.environ[STRIPE_LIVE_PRICE_PLAN_*_MONTHLY]` — no legacy fallback.

## 5. Root cause

**DUPLICATE_VALUES_CONFIRMED** — Portfolio and Professional monthly env vars share the same runtime fingerprint; Solo is distinct.

## 6. Remediation

1. Set `STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY` to the £79 monthly price (distinct from Portfolio).
2. Redeploy/restart backend API service.
3. Re-run this verify script.

## 7. Verification

- `/api/billing/plans`: 200
- `/api/client/entitlements`: 200
- Checkout: blocked (400 STRIPE_MODE_MISMATCH duplicate) until Pro monthly fixed

See `runtime_fingerprint_verify_01.json` for full masked evidence.
