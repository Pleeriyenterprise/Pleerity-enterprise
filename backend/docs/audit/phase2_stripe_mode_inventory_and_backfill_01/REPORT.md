# Stripe mode governance — Phase 2 inventory, remediation & Phase 3 client remediation

**Latest closeout:** PHASE-3-STRIPE-MODE-CLIENT-REMEDIATION-01 (2026-06-02)  
**Classification:** `CLIENT_REMEDIATION_REQUIRED`  
**Prior:** `MODE_UNVERIFIED_BACKLOG`

## Phase 3 summary

Client-by-client remediation worklist generated for **33** staging billing rows. All classified **`REGENERATE_CHECKOUT_REQUIRED`** (no webhook evidence, checkout sessions lack persisted `stripe_mode`). **50** orphaned checkout sessions classified **`requires_regeneration`** (pending, missing mode). No bulk mode assignment performed.

One **admin-set-mode** proof executed via staging API (`backfill_authoritative_mode`, `stripe_mode=test`). Deploy must include `admin_verified` source + `$unset` of `MODE_UNVERIFIED` for preflight to pass after remediation (commit pending deploy).

## Phase 3 — Client remediation worklist

| Recommended action | Count |
|--------------------|------:|
| REGENERATE_CHECKOUT_REQUIRED | 33 |

Per client (redacted): subscription/customer IDs present, checkout sessions exist but **without** authoritative `stripe_mode`, **no** webhook livemode evidence, `MODE_UNVERIFIED` containment active.

Artifact: `client_remediation_worklist.json`

## Remediation policy

Admin-set-mode allowed only with manual Stripe dashboard verification, webhook/checkout evidence, or documented admin confirmation — **never** deployment mode alone or ID prefix.

Artifact: `remediation_policy.json`

## Regenerate checkout flow

Documented safe path via `POST /api/billing/checkout` — persists `stripe_mode` on new `checkout_sessions`, preserves client/CRN, no duplicate subscription automation.

Artifact: `regenerate_checkout_runtime.json`

## Admin-set-mode (single-client proof)

| Check | Result |
|-------|--------|
| API POST admin-set-mode | 200 |
| action | `backfill_authoritative_mode` |
| stripe_mode | `test` |
| confidence | `authoritative` |
| reason required | yes |

Artifact: `admin_set_mode_runtime.json`

## Orphaned checkouts

| Classification | Count |
|----------------|------:|
| requires_regeneration | 50 |

No automatic deletion.

Artifact: `orphaned_checkout_runtime.json`

## Upgrade/downgrade retest

| Scenario | Result |
|----------|--------|
| Still MODE_UNVERIFIED row | Pass (customer-safe block) |
| Admin-set-mode client preflight | Fail until deploy includes MODE_UNVERIFIED unset fix |

Artifact: `upgrade_downgrade_retest_runtime.json`

## Customer copy

Blocked: *"Your billing record needs to be refreshed before plan changes can continue."*

Regeneration copy documented without Stripe jargon.

Artifact: `customer_copy_runtime.json`

## Production inventory

**Blocked** — `PRODUCTION_MONGO_URL` not provided.

Artifact: `production_inventory_status.json`

## Path to VERIFIED_OPERATIONALLY

1. Production inventory (`--production-mongo-url`)
2. Deploy Phase 3 code (`admin_verified`, worklist service, MODE_UNVERIFIED unset on authoritative write)
3. Remediate clients via regenerate checkout or verified admin-set-mode
4. Re-run upgrade/downgrade retest on remediated + unverified samples
5. Confirm authoritative_mode_coverage > 0

## Implementation commits

- `a06c082d` — Phase 1 containment
- `b41fdcf6` — Phase 2 inventory/backfill
- `35e68d7f` — Phase 2 remediation closeout
- Phase 3 — client remediation service + closeout (this commit)
