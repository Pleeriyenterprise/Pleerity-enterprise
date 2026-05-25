# Rent Operations Tenancy Authority Remediation

**Audit ID:** `rent_operations_tenancy_authority`  
**Date:** 2026-05-20  
**Classification:** `PARTIAL` (implementation + unit tests complete; staging browser verification pending)

## Root cause

Rent Operations Phase 1 treated **property** as the primary authority. Tenancy was optional metadata, schedules could be recreated without lineage, ledger periods deduplicated at property level (not schedule/tenancy), and the UI allowed payments without ledger context. That produced **RENT_AUTHORITY_DRIFT**, **PAYMENT_ATTRIBUTION_FAILURE**, and **TRUST_RISK_PRESENT** (false failed-success on schedule create).

## Implementation

### Authority chain

`Property → Tenancy (property_tenancies) → Tenant(s) → Rent Schedule → Ledger Periods → Payments`

- `rent_tenancy_authority_service.py` — tenancy CRUD, validation, move-out closure
- Schedules require `tenancy_id` or explicit `is_external_payer` + name
- One active schedule per `(client, property, tenancy, rent_type)`
- Ledger materialisation keyed by `schedule_id` + `period_key`
- Payments require `ledger_id`; `tenancy_id` stored on payment rows
- Unallocated amounts persisted to `rent_unallocated_payments`

### Schedule creation honesty

- `POST /schedules/preview` — period count, range, disclosure string
- `idempotency_key` on create (replay-safe)
- Partial recovery response when periods exist after error

### UI

- `RentScheduleSetupModal` — tenancy picker, preview, external payer option
- `RecordPaymentModal` — ledger authority context; no detached header payment
- Occupancy panel — **Enable rent tracking** deep link to rent ops with `property_id` + `setup=1`
- Rent Operations — monitoring surface; not tenancy creation authority

## Tests

- `backend/tests/test_rent_tenancy_authority.py` (new)
- Existing `test_rent_operations.py`, `test_client_rent_operations_http.py`

## Verification status

| Gate | Status |
|------|--------|
| Unit/API contract | Pass |
| Staging browser E2E | Pending post-deploy |
| VERIFIED_OPERATIONALLY | Not yet |

See `watchlist.md` for remaining items.
