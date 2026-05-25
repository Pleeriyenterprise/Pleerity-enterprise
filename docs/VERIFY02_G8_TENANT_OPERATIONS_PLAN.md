# VERIFY-02 G8 — Tenant Operations (planned, not executed)

**Programme:** `PRELAUNCH-OPS-RUNTIME-VERIFY-02` (optional extension family)  
**Owner:** `ops_control_g8_tenant_operations` (proposed)  
**Status:** `NOT_EXECUTED` — implementation layer `IMPLEMENTATION_READY` only

## Purpose

Verify tenant operational coherence after property-scoped aggregation layer ships, without breaking F7 tenant portal segregation or G1–G7 authority.

## Prerequisites

- G0–G7 `VERIFIED_OPERATIONALLY` on pilot `6fd5ac4c_d35a58ae` (current baseline).
- F7 tenant portal `VERIFIED_OPERATIONALLY` (VERIFY-01).
- Property occupancy tab deployed to staging/production.

## Checkpoints (draft)

| ID | Checkpoint |
|----|------------|
| G8-BOOT | `/tenants` + property occupancy tab reachable; refresh persistence |
| G8-AUTH | Tenant cannot call landlord rent/issue mutation APIs (regression) |
| G8-RENT-SYNC | Property occupancy rent section matches `rent_ledger_service` summary |
| G8-MAINT-SYNC | Open tenant-reported issues match maintenance list filter |
| G8-SCHEDULE | Calendar visit for property appears on occupancy panel when API has event |
| G8-TRUTH | reported ≠ resolved; scheduled ≠ fixed; reminder ≠ paid |
| G8-PORTAL-TRUST | No landlord leakage of tenant session secrets |
| G8-COGNITION | No false reassurance when arrears + open issues exist |
| G8-G9/G10 | No duplicate alert inflation; authority tags preserved |

## Classifications (allowed)

- `VERIFIED_OPERATIONALLY`
- `FAIL_OPERATIONAL`
- `TRUST_RISK_PRESENT`
- `PROJECTION_AUTHORITY_DRIFT`
- `COGNITIVE_TRUST_RISK`
- `BLOCKED`

## Artifacts (proposed bundle)

`backend/docs/audit/ops_runtime_g8_tenant_operations_6fd5ac4c_d35a58ae/`

- `tenant_operations_surface_boot.json`
- `tenant_authority_segregation.json`
- `tenant_rent_sync.json`
- `tenant_maintenance_sync.json`
- `tenant_schedule_coherence.json`
- `tenant_portal_trust.json`
- `tenant_operational_cognition.json`
- `07_classification.json`

## Explicit exclusions

- Full tenancy platform redesign
- CRM / marketing automation
- Re-proof F7 end-to-end journeys (reference F7 bundle only)

## Execution trigger

Product sign-off on `tenant_operations_architecture.md` + staging deploy of occupancy summary API and UI tab.
