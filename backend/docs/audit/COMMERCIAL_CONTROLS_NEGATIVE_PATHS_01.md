# Commercial Controls — Negative Paths

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_NEGATIVE_PATHS_01.md`  
**Date:** 2026-08-15

## Spinner contract

Every path must end in SUCCESS or ERROR. Permanent spinner was caused by an unresolved step-up Promise. After the modal host + axios timeout:

| Failure | Spinner | Data | Retry |
| --- | --- | --- | --- |
| Validation (reason < 10, duration cap, confirm unchecked) | Never starts / stops immediately | Preserved | Yes |
| Step-up cancelled | Stops | Preserved | Yes |
| 400/403/409 from execute | Stops; error message from `apiErrorMessage` | Preserved | Yes (new confirmation token) |
| Axios timeout (60s) | Stops; do-not-assume-success copy | Preserved | Operator must re-read state first |
| Duplicate active exception | Stops; `ACTIVE_EXCEPTION_EXISTS` | — | Revoke first |

## Backend negatives (code / unit)

| Case | Expected | Proven |
| --- | --- | --- |
| Missing / short reason | 400 from governance `ensure_action_reason` | Policy unit tests; schema `min_length=10` |
| Confirmation missing | consume token fails | Prior billing-panel runtime (`execute_without_governance_blocked` 422, 2026-06-05) |
| No step-up | 403 `STEP_UP_REQUIRED` | Code + prior runtime `execute_without_step_up_blocked` |
| Duration over max (grace 31) | `VALIDATION_FAILED` | Unit `test_duration_cap_grace_rejects_over_max` |
| Duplicate active | `ACTIVE_EXCEPTION_EXISTS` | Unit transition + DuplicateKeyError mapping |
| Revoke with no active | `NO_ACTIVE_EXCEPTION` | Unit |
| Client role | Admin routes `require_owner_or_admin` | Route dependency; client token not runtime-tested this run |
| Unauthenticated | 401/403 | Staging probe not run (login locked before harness) |
| Stripe failure | Isolated; exception remains | Code timeout wrapper; not runtime-injected |
| Email failure | Isolated; warning toast | Code; not runtime-injected |
| DB duplicate insert | Unique index + mapped error | Unit on DuplicateKeyError; index not live |
| Network timeout | Axios 60s | Code; not runtime-injected |
| Stale frontend | Backend re-loads signals; duplicate blocked | Code |

## Staging this exercise

Negative-path HTTP probes were **not** executed because admin login returned 423 before the harness started.
