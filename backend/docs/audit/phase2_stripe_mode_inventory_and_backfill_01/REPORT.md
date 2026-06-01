# PHASE-2-STRIPE-MODE-INVENTORY-AND-BACKFILL-01

## Objective

Recover authoritative Stripe environment truth across persisted billing entities without destructive migration or unsafe automatic billing mutation.

## Scope delivered

| Part | Deliverable | Status |
|------|-------------|--------|
| 1 | Expanded read-only inventory (`GET /api/admin/billing/stripe-mode-inventory?expanded=true`) | Implemented |
| 2 | `stripe_mode_backfill_service.py` — authoritative resolution order | Implemented |
| 3 | Safe backfill engine (dry-run + execute, authoritative only) | Implemented |
| 4 | MODE_UNVERIFIED governance — blocks plan changes, customer-safe message | Implemented |
| 5 | Legacy caller convergence (intake_draft, jobs, Clearform) | Implemented |
| 6 | Admin remediation endpoints + classification codes | Implemented |
| 7 | Webhook event persistence (`livemode`, `environment_source`, `event_verification_status`) | Implemented |
| 8 | Commercial entitlement drift surfacing + remediation guidance | Implemented |
| 9 | Observability (`stripe_mode_backfill_audit`, `stripe_mode_inventory_metrics`) | Implemented |
| 10 | Closeout harness for staging/prod inventory | Implemented |
| 11 | Regression tests (`test_stripe_mode_backfill.py`, containment extensions) | 22 passed |
| 12 | Audit artifacts in this directory | See manifest |

## Authoritative resolution order

1. Verified webhook `livemode` on related `stripe_events`
2. Persisted checkout session `stripe_mode`
3. Verified persisted / deployment-at-creation metadata
4. Stripe API retrieve in each environment (never ID-prefix inference)
5. Explicit admin remediation
6. **UNKNOWN** → `MODE_UNVERIFIED` (no silent default)

## Forbidden (enforced)

- Automatic subscription migration, cancellation, recreation
- Silent environment switching
- Prefix-only inference (`sub_` ≠ live)

## Admin endpoints

- `GET /api/admin/billing/stripe-mode-inventory?expanded=true`
- `GET /api/admin/billing/stripe-mode-remediation/{client_id}`
- `POST /api/admin/billing/stripe-mode-backfill` (dry-run default)
- `POST /api/admin/billing/stripe-mode-remediation/{client_id}/admin-set-mode`
- `GET /api/admin/billing/stripe-mode-legacy-callers`

## Customer copy (MODE_UNVERIFIED / drift)

> Your billing record needs to be refreshed before plan changes can continue.

## Remediation classifications

- `REGENERATE_CHECKOUT_REQUIRED`
- `INVALID_SUBSCRIPTION_REFERENCE`
- `LEGACY_TEST_SUBSCRIPTION`
- `MODE_UNVERIFIED`
- `PORTAL_RELINK_REQUIRED`
- `CUSTOMER_RECONCILIATION_REQUIRED`

## Harness

```bash
cd backend
python scripts/phase2_stripe_mode_inventory_closeout.py \
  --mongo-url "$MONGO_URL" --db-name pleerity_staging
```

## Staging inventory (live Mongo, read-only)

Executed against `pleerity_staging` on 2026-06-01:

| Category | Count |
|----------|------:|
| missing_stripe_mode | 33 |
| orphaned_checkout_sessions | 50 |
| mixed_customer_subscription_mode | 0 |
| webhook_mode_conflicts | 0 |

**Authoritative mode coverage:** 0% — legacy rows lack webhook/checkout evidence in DB; dry-run backfill classifies all 33 as `MODE_UNVERIFIED` (no silent default).

**Production inventory:** Not executed — see `production_drift_inventory.json` (blocked pending credentials).

## Classification

**`MODE_UNVERIFIED_BACKLOG`** — framework operational; staging backlog requires admin remediation (webhook evidence missing for legacy rows; use explicit `admin-set-mode` or regenerate checkout after deploy).

Upgrade to **`VERIFIED_OPERATIONALLY`** when: production inventory executed, authoritative backfill applied where evidence exists, production deploy verified.
