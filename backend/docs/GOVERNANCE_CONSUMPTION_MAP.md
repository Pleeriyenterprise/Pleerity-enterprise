# Governance consumption map

**Navigation:** For full governance topology, tiers, recovery map, and document inventory, see **[GOVERNANCE_INDEX.md](./GOVERNANCE_INDEX.md)** (canonical router). This file remains the **surface-level consumption** inventory for CI.

**Status:** ACTIVE (TIER_2 — partial inventory)  
**Authority Level:** TIER_2  
**Related Docs:** GOVERNANCE_INDEX.md, WORKFLOW_BEHAVIOUR_GOVERNANCE.md, governance_coverage_registry.py  
**Last Governance Review:** 2026-05-16  
**Non-goals:** This file is not runtime configuration; it does not replace `WORKFLOW_BEHAVIOUR_GOVERNANCE.md` or registry authority.

## Legend

| Tag | Meaning |
|-----|---------|
| **GOVERNED** | Contract is sourced from or aligned with server governance / decision-record / audit diagnostics. |
| **PARTIALLY_GOVERNED** | Mixed: server contracts apply in part; local fallbacks, duplicated semantics, or client-only inference remain. |
| **UNGOVERNED** | No systematic linkage to workflow governance contracts today (risk of semantic drift). |

## A. Runtime systems that already consume workflow governance

| System | Consumption | Notes |
|--------|-------------|--------|
| **Audit pipeline (admin)** | **GOVERNED** | `requirement_workflow_audit.compute_workflow_mismatch_flags` + `governance_augment_mismatch_flags` enrich admin payloads (`apply_workflow_reference_audit`). |
| **Drift audit script** | **GOVERNED** | `scripts/registry_workflow_drift_audit.py` exercises `effective_evidence_resolution`, resolver envelope, and workflow mismatch flags. |
| **Governance validation (Phase 1)** | **GOVERNED** | `governance_validation_engine.py` + `governance_coverage_registry.py` (CI). |

## B. Systems still using local fallback semantics

| System | Status | Notes |
|--------|--------|--------|
| **Resolver take_action** | **PARTIALLY_GOVERNED** | `requirement_action_resolver` uses `effective_evidence_resolution` and engine rows; workflow **reference** audit is separate. Client parity relies on `take_action` contract, not `get_workflow_capabilities()` at runtime. |
| **Evidence defaults** | **PARTIALLY_GOVERNED** | `DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE` when registry omits `evidence_resolution` — documented drift vs decision-record reference. |
| **Compliance score drivers** | **PARTIALLY_GOVERNED** | Canonical guards in `compliance_score`; not wired to `EXECUTION_SEMANTICS_METADATA` or reporting semantics. |
| **Gap engine** | **PARTIALLY_GOVERNED** | Truth/scoring paths; not explicitly keyed to workflow execution contracts. |

## C. Surfaces with duplicated or parallel semantic logic

| Location | Status | Notes |
|----------|--------|--------|
| **Frontend CTA** | **PARTIALLY_GOVERNED** | `frontend/src/utils/requirementTakeActionResolver.js` mirrors server intent/labels — must stay in sync with resolver (see resolver module docstring). |
| **Frontend status / KPI copy** | **PARTIALLY_GOVERNED** | “Missing documents”, score nudges, etc. are presentation-layer; not derived from `workflow_behaviour_governance` helpers. |
| **Command Centre / Today strings** | **PARTIALLY_GOVERNED** | e.g. `clientCommandCenter.js` uses local copy for “best next move”; not workflow-class aware. |

## D. APIs / surfaces partially ungoverned

| Surface | Status | Notes |
|---------|--------|--------|
| **Requirements list API** | **PARTIALLY_GOVERNED** | Enriched from resolver + registry; workflow diagnostics stripped for tenant client (`strip_workflow_diagnostics_from_payload`). |
| **Property compliance matrix** | **PARTIALLY_GOVERNED** | Same enrichment path as requirements; document-centric filters are not workflow-class keyed in UI. |
| **Needs attention subsets** | **PARTIALLY_GOVERNED** | Priority streams use engine + dates; workflow execution semantics not first-class. |
| **Work queue / unified tasks** | **PARTIALLY_GOVERNED** | Maps requirement rows to actions; resolver-driven but not governance-validation wrapped. |
| **Reports / exports** | **PARTIALLY_GOVERNED** | Reporting semantics documented; export builders do not yet consume `GOVERNANCE_SURFACE_REGISTRY`. |
| **Reminder generation** | **UNGOVERNED** | Schedulers/jobs not aligned to execution-semantics registry in Phase 1. |

## Summary table (quick reference)

| Area | Tag |
|------|-----|
| Resolver | PARTIALLY_GOVERNED |
| Requirements list | PARTIALLY_GOVERNED |
| Score drivers | PARTIALLY_GOVERNED |
| Command centre | PARTIALLY_GOVERNED |
| Today / tasks | PARTIALLY_GOVERNED |
| Work queue | PARTIALLY_GOVERNED |
| Reports / exports | PARTIALLY_GOVERNED |
| Property compliance matrix | PARTIALLY_GOVERNED |
| Needs attention | PARTIALLY_GOVERNED |
| Audit pipeline (admin) | GOVERNED |
| Frontend CTA logic | PARTIALLY_GOVERNED |
| Frontend status wording | PARTIALLY_GOVERNED |
| Reminder generation | UNGOVERNED |
| Gap engine | PARTIALLY_GOVERNED |

## Phase 1 guardrails (machine-readable)

See `services/governance_coverage_registry.py` (`GOVERNANCE_SURFACE_REGISTRY`) and `services/governance_validation_engine.py` for CI-safe checks. Observability hooks: `services/governance_observability.py` (optional callers; no vendor telemetry).
