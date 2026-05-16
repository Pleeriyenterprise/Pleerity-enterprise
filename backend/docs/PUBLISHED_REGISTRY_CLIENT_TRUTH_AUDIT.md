# Published Registry Client-Truth Source Audit

**Status:** ACTIVE (TIER_2)  
**Authority Level:** TIER_2 — migration policy + materialisation/visibility timing  
**Related Docs:** `GOVERNANCE_INDEX.md`, `LAUNCH_AUTHORITY_TRACKER.md` (A1–G2), `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`  
**Last Governance Review:** 2026-05-16

This inventory classifies requirement generation and consumption paths for the migration to published-registry client truth.

## Source Classification

- **Client-facing active obligation**
  - `backend/services/requirement_client_runtime_surface.py`
  - `filter_requirement_rows_for_client_runtime_surfaces()`
  - `project_requirement_row_client_runtime()`
- **Internal fallback**
  - `backend/services/compliance_requirement_registry.py`
  - `backend/services/requirement_catalog.py`
- **Migration compatibility**
  - `backend/services/provisioning.py` (`requirement_generation_source=requirement_rules`)
  - `backend/services/compliance_governed_rules_service.py`
- **Historical/audit only**
  - Persisted legacy rows in `requirements` with linked entities (`documents`, `work_orders`, `reminder_item_state`, `invoices`)
- **Test fixture only**
  - Direct seeded requirement rows in backend tests that bypass planner/published registry

## Downstream Consumers Audited

- Scoring: `backend/services/compliance_score.py`, `backend/services/compliance_scoring_service.py`
- Reminders: `backend/services/reminder_truth_service.py`
- Gap stream and priority: `backend/services/compliance_gap_sync.py`, `backend/services/client_priority_stream.py`, `backend/services/unified_tasks_service.py`, `backend/services/command_center_service.py`
- Reporting and digest: `backend/services/reporting_service.py`, `backend/services/professional_reports.py`, `backend/services/monthly_digest_assembly_service.py`

## Migration Policy

- New/active client-visible obligations must have active published registry eligibility.
- Legacy rows without published eligibility are retained as:
  - `mapped_readonly` / `unmapped_readonly` when linked history exists
  - `hidden_deprecated` when no linked history exists
- No hard deletion of historical rows in this migration.

## Materialisation timing (obligation creation)

| Stage | Creates `requirements` rows? | Authority |
|-------|------------------------------|-----------|
| Intake submit (`routes/intake.py`) | **No** — creates `clients` + `properties` only | Intake gating doc |
| Stripe checkout / webhook → provisioning job | **Yes** — when `provision_client_portal_core` completes | `services/provisioning.py` → `_generate_requirements` → `materialize_requirements_for_property` |
| Property PATCH (e.g. `is_hmo`, jurisdiction) | **Yes** — rematerialise + recalc path | `routes/properties.py` |
| Registry publish | **No fleet rematerialise** | `REMATERIALISATION_INFO` on publish responses; per-property sync required |

**Launch recovery units:** **A2** (provisioning repair), **A3** (controlled sync). Proof: `RUNBOOK_CONTROLLED_BETA_OPERATIONS.md` §12.7. Implementation: `LAUNCH_AUTHORITY_TRACKER.md` § Recovery unit implementation contract (end-to-end; no partial DONE).

## Client runtime visibility gates

When `fetch_active_published_registry_entries` returns a **non-null** map (including `{}`), catalog-backed rows need a **published overlay** for the property’s portfolio label **or** `legacy_readonly_visible` / mapped readonly state (`requirement_client_runtime_surface.py`).

**Exclusion reasons (admin explain):** `not_required_row`, `client_surface_hidden`, `primary_action_hidden`, `archived_registry_metadata`, `draft_or_unpublished_materialization`, `row_jurisdiction_mismatch`, `not_in_planner_membership`, missing published overlay (implicit).

**Launch recovery units:** **B1** (fix proven exclusion), **B2** (registry overlay coverage). **Do not** weaken overlay gate without written governance sign-off.

**Historical audit note:** `scripts/ghost_vs_published_report.json` documented types visible in Mongo but dropped by filter (`co_alarms`, `right_to_rent`, `smoke_alarms`, etc.) — typical **B-only** pattern when raw rows exist.

## Controlled sync after publish

| Endpoint | Actor | Purpose |
|----------|-------|---------|
| `POST /api/admin/properties/{property_id}/requirements/sync-from-registry` | Staff | Reconcile one property to active published plan |
| `POST /api/properties/{property_id}/requirements/sync` | Client (own property) | Same core materialisation; audited |

- **No** automatic rematerialisation of all properties on publish.
- **A3** verification: raw rows align with `build_requirement_plan_for_property`; unexpected mass `NOT_REQUIRED` is a stop condition.
- Prefer sync + registry publish over raw Mongo edits.

### NOT_REQUIRED persistence vs reconcile (B1)

- **Operator-curated** `NOT_REQUIRED` (override, `not_applicable_audit_reason` ≥10 chars, `OPERATOR_OVERRIDE` source) is preserved on materialise.
- **Automated** `not_required_reason` presets (e.g. bulk `not_applicable`) on **in-plan** types are reopened to `UNKNOWN`/`PENDING` when the type is in the current planner.
- **`reconcile_obsolete`**: types not in `planned_types` converge to `NOT_REQUIRED` with `registry_metadata.reconciled_obsolete` + `automated_not_required` provenance; repeat sync must **skip** already-reconciled rows (write-idempotent).
- Client visibility remains governed by `requirement_client_runtime_surface` — B1 fixes persistence, not filter bypass.

### Wales HMO pilot visibility posture (2026-05-16)

Product/governance sign-off for tenant `6fd5ac4c…` / property `d35a58ae…`:

- **Accepted client-visible obligation families:** 8 (`eicr`, `legionella`, `epc`, `gas_safety`, `hmo_license`, `fire_alarm`, `hmo_fire_risk_evidence`, `occupation_contract`).
- **`emergency_lighting` and `fire_extinguisher`:** **intentionally non-visible** — do not publish overlays, expand planner, or weaken runtime gates for this pilot.
- Residual explain exclusions vs `raw_count=21` are **expected** (alias dedupe, reconcile obsolete, out-of-planner, legacy rows) unless a **new** tenant class requires overlay work (**B2**).

## Empty published map governance

If the active published snapshot is **empty** but non-null, catalog registry rows **without** `legacy_readonly_visible` are **excluded** from client surfaces (unit: `test_published_mode_excludes_non_published_non_legacy_row`). Operations must either publish coverage (**B2**) or explicitly accept readonly/legacy buckets — not treat as “missing materialisation” without checking **raw_count** first.

