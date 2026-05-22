# CONDITION_STANDARD_ACTIVE_STANDARD — OPS family (Phase 1 foundation)

**Status:** Phase 1 runtime foundation + **bounded runtime-legitimacy fix** (2026-05-22).  
**OPS closure (repairing_standard, Scotland pilot):** Same-run browser attestation 2026-05-22 — matrix, inspect, CTA, disclosure, refresh, **`?open=resolve` → `/operations/issues`** **verified** (`ops_verify_03_browser_attestation.json`). Classification: **`VERIFIED_OPERATIONALLY`** for `repairing_standard` only. FFHH **not** run.

## Family identity

| Field | Value |
|-------|--------|
| OPS family | `CONDITION_STANDARD_ACTIVE_STANDARD` |
| Programme id | `PRELAUNCH-OPS-VERIFY-CONDITION-STANDARD-01` |
| Proof mode | `operational_convergence` |
| Obligations in scope | `fitness_for_human_habitation`, `repairing_standard` |

## Architectural rules (mandatory)

- Hybrid composite standards; **operational convergence** is authoritative.
- Closure inputs: maintenance issues, work orders, risk signals, compliance gaps.
- Supporting uploads **never** independently close the standard.
- Assets are **not** authoritative closure sources in Phase 1.
- No global planner auto-materialisation.

## Runtime-legitimacy fix (2026-05-22, bounded)

**Root cause:** `filter_requirement_rows_for_client_runtime_surfaces` treated `requirement_generation_source=condition_standard_pilot_ops` as unknown and required catalog planner membership; `repairing_standard` is intentionally outside planner emission.

**Fix:** `evaluate_condition_standard_pilot_runtime_legitimacy` / `is_condition_standard_pilot_runtime_legitimate` in `services/condition_standard_pilot_materialisation.py`; early pass in `requirement_row_passes_client_runtime_surface_gates` when **all** hold:

- `workflow_family` + `ops_verification_family` = `CONDITION_STANDARD_ACTIVE_STANDARD`
- `requirement_generation_source` = `condition_standard_pilot_ops`
- allowlisted pilot tuple + `materialisation_provenance.source` = `CONDITION_STANDARD_PILOT_MATERIALISATION`
- jurisdiction gate + published registry overlay for property
- `client_surface_visible` ≠ false

**Not changed:** global planner bypass; FFHH OPS; authority semantics; upload closure rules.

**Tests:** `tests/test_condition_standard_pilot_runtime_surface.py`

## Phase 1 delivered

1. **Controlled pilot materialisation** — `services/condition_standard_pilot_materialisation.py`; admin `POST …/condition-standard-pilot-materialise`; allowlist only.
2. **Runtime enrichment** — `active_standard_status_summary` with granular states + `state_label` + `ops_verification_family`.
3. **Authority / lifecycle hardening** — operational-followup guard on all authority paths; lifecycle blocks `VERIFIED` for condition standards with open signals.
4. **UX semantics** — truthful matrix/modal/inspect copy; forbidden verified/compliant language.
5. **Registry CTA alignment** — repairing standard published snapshot: `view_guidance` (runtime resolver already issues/WO-primary).
6. **OPS readiness helpers** — `services/ops_condition_standard_readiness.py`.
7. **Inspect panel** — `ConditionStandardOperationalInspectPanel` in requirement intelligence modal.

## Materialisation strategy

- Rows are **persistent** requirement documents with stable `requirement_id`.
- Only **explicit pilot tuples** may be inserted/updated via pilot materialisation path.
- Prerequisites per obligation: jurisdiction gate + `tenancy_active` on property.
- Do **not** silently materialise fleet-wide.

### Pilot allowlist (2026-05-20)

| Obligation | client_id | property_id |
|------------|-----------|---------------|
| `fitness_for_human_habitation` | `6bcc43c0-16f4-46a5-adf4-26693a0919d0` | `3a69dcbd-74fd-4291-839b-3d52750598a1` |
| `repairing_standard` | `ec0b091b-105d-4b78-9711-7ab143999cef` | `def23b30-efa5-41f9-a9cc-7fb69f9e9024` |

## OPS checkpoints (future execution)

`CS-PRE` … `CS-O14` — issue/WO/risk/gap lifecycle, upload regression, matrix/authority coherence, refresh persistence, inspect visibility.

## Classifications

`VERIFIED_OPERATIONALLY`, `ASYNC_CONVERGENCE_PARTIAL`, `USER_VISIBLE_GAP`, `TRUST_RISK_PRESENT`, `SYSTEM_OUTCOME_UNPROVEN`, `TEST_DATA_REQUIRED`.

## What is VERIFIED vs NOT

| Item | Status |
|------|--------|
| Governance capability profile | **Verified** (code + tests) |
| Runtime convergence read-model | **Verified** (unit/integration tests) |
| Pilot materialisation path | **Implemented** — requires admin invoke per pilot |
| Runtime filter + API + compliance-detail matrix | **Verified** |
| Browser matrix / inspect / CTA / disclosure / refresh | **Verified** (2026-05-22 attestation) |
| Browser `?open=resolve` deeplink (`repairing_standard`) | **Verified** (2026-05-22; routes to issues/remediation) |
| End-to-end `VERIFIED_OPERATIONALLY` (`repairing_standard`) | **Met** (2026-05-22) |
| Launch readiness | **NOT READY** |

## Remaining limitations

- No asset-level synthesis into condition row.
- Planner does not auto-emit FFHH/RS.
- Staging may still show **0 rows** until pilot materialisation is invoked.
- Score impact remains distributed operational — not certificate closure.

## Deferred

- Asset-native rollups into `active_standard_status_summary`.
- Fleet materialisation / jurisdiction-wide rollout.
- OPS programme execution bundles.
