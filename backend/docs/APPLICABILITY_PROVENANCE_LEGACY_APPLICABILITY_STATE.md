# Legacy `applicability_state` vs provenance (PR3)

## Contract

- **`pipeline_applicability_state`** (flat + nested) is written only from **pipeline** paths (materialization / policy backfill `resolve_policy_facts`), never from operator override APIs (PR3 has no operator API yet).
- **`effective_applicability_state`** and **`applicability_resolution_source`** are produced by the **selector** (`build_provenance_mongo_set`), which may diverge from pipeline when `operator_override_active` is true (future operator layer).
- **Legacy `applicability_state`** on `requirements` is **dual-written** to match **`effective_applicability_state`** on every pipeline-driven merge (`merge_provenance_into_requirement_patch`). Existing code that still reads `applicability_state` therefore sees the same obligation semantics as **effective**, not a second competing source.

## Until consumer migration

Runtime reads that have not been migrated should continue to use **`applicability_state`**; it remains populated and aligned with **effective**. New analytics and internal tooling should prefer **`pipeline_applicability_state`** vs **`effective_applicability_state`** explicitly.

## Auditing

When pipeline or effective applicability (or resolution source) changes, an append-only row is written to **`applicability_resolution_audit`** (best-effort: failures are logged and do not roll back the requirement write).

## PR4 operator commands (internal admin only)

Owner/Admin: `POST /api/admin/ops/clients/{client_id}/requirements/{requirement_id}/applicability-operator` with JSON `command` (`MARK_REQUIRED` | `MARK_NOT_REQUIRED` | `REVOKE_OVERRIDE`), required `resolution_reason_code` (closed enum), optional `notes`. **Pipeline** fields are never overwritten by these commands; **effective** + legacy **`applicability_state`** follow the selector. Each command appends an audit row.
