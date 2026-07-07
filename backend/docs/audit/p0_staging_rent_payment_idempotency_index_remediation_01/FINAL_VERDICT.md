# P0 Staging Rent Payment Idempotency Index Remediation

**Programme:** P0-STAGING-RENT-PAYMENT-IDEMPOTENCY-INDEX-REMEDIATION-01  
**Environment:** `pleerity_staging` only (no production changes)  
**Executed:** 2026-07-07T21:45:39Z  

## Verdict

**`RENT_PAYMENT_IDEMPOTENCY_RESTORED`**

## Root cause

The partial unique index `(client_id, idempotency_key)` on `rent_payments` could not be built because five duplicate document pairs already existed. All duplicates originated from the **OPS-RESIL** operations resilience audit (`operations_resilience_and_concurrency_audit_01_execute.py`), which intentionally fired concurrent rent payment POSTs with the same idempotency key to probe race behaviour. The application-level idempotency check in `record_payment()` is not atomic with insert, so concurrent requests both succeeded before the index existed.

## Audit findings

| Metric | Value |
|--------|-------|
| Duplicate groups | 5 |
| Exact duplicates | 5 |
| Conflicting duplicates | 0 |
| Affected client | `6fd5ac4c-3fd4-4112-ade7-156977deb49f` (Nancy staging) |
| Affected ledger | `rlp_eaa80d462b1c` |
| Duplicate amount per pair | £5.00 (500 minor) |
| Total duplicate inflation removed | £25.00 (2500 minor) |

All five groups were **exact duplicates** (identical amount, ledger, schedule, property, reference). Earliest `created_at` record retained in each group; later copy archived to `rent_payments_idempotency_remediation_archive_01` then deleted.

## Remediation actions

1. Archived 5 duplicate documents to `rent_payments_idempotency_remediation_archive_01`
2. Deleted 5 duplicate `rent_payments` rows (kept canonical earliest per group)
3. Recalculated ledger `rlp_eaa80d462b1c` — outstanding balance corrected from **37500 → 40000** minor (+2500), confirming duplicate payments had deflated outstanding balance
4. Rebuilt unique partial index `client_id_1_idempotency_key_1`

## Verification

| Check | Result |
|-------|--------|
| Index exists with unique + partial filter | Pass |
| Remaining duplicate groups | 0 |
| Duplicate insert rejected (E11000) | Pass |
| Distinct idempotency_key insert succeeds | Pass |
| Ledger totals not inflated by duplicates | Pass (recalc applied) |

## Regression tests

Added `tests/test_p0_rent_payment_idempotency_01.py`:

- Service-level idempotent replay returns prior payment without insert
- Index partial filter contract (`idempotency_key` must be string type)
- `_ensure_compound_idempotency_index` creates unique partial index

## Evidence files

- `DUPLICATE_AUDIT.json` — structured duplicate inventory
- `REMEDIATION_REPORT.json` — full execution log with document IDs
- `REMEDIATION_REPORT.md` — summary
- `scripts/p0_staging_rent_payment_idempotency_remediation_01.py` — repeatable remediation script

## Scope boundaries

- Staging/develop only
- No production database changes
- No merge to `main`
- Platform-Wide Release Readiness Audit not started
