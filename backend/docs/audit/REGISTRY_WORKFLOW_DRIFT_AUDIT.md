# Live registry / runtime workflow drift audit

**Findings (deduped):** 4
**Scenarios:** 113 (canonical codes × jurisdictions)

**Scope note:** No published-registry Mongo overlay — uses code defaults + decision-record `client_workflow_class` fallbacks only. Production drift may differ where registry publishes `registry_metadata.evidence_resolution`.

## Methodology

Synthetic requirement rows per canonical code × jurisdiction (grid trimmed for Scotland-only repairing/lead-testing, non-Scotland fitness, and excludes system classification slugs per decision-record section 5.8); effective_evidence_resolution + resolve_take_action_envelope + enrich_take_action_envelope_for_client; compute_workflow_mismatch_flags with decision-record reference (no published registry overlay); explicit policy-vs-reference checks; engine vs external-assessment heuristic for lead_testing.

## Counts by drift type

- **CANONICAL_IDENTITY_DRIFT:** 4

## Counts by severity

- **LOW:** 4

## Findings by workflow class (runtime)

### GUIDED_DECLARATION

- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (england): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (scotland): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (wales): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (northern_ireland): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)


## Governance Coverage Gaps

**Surfaces at enforcement NONE (highest drift risk):** .

**Surfaces at PARTIAL enforcement (fallback or duplicate semantics likely):** command_centre, frontend_cta, frontend_status, gap_engine, needs_attention, property_compliance_matrix, reminder_generation, reports_exports, requirements_list, resolver, score_drivers, today_tasks, work_queue.

**STRICT governance surfaces:** audit_pipeline.

**Surfaces flagged as using local fallback logic:** command_centre, frontend_cta, frontend_status, gap_engine, needs_attention, property_compliance_matrix, reminder_generation, reports_exports, requirements_list, resolver, score_drivers, today_tasks, work_queue.

## Frontend Semantic Drift Risks

- Client CTA resolver (`frontend/src/utils/requirementTakeActionResolver.js`) duplicates resolver intent mapping — misalignment produces drift not visible in backend-only audits.
- Dashboard / Command Centre copy uses document-centric language (e.g. “Missing documents”) without workflow-class qualifiers.

## Duplicate Runtime Semantic Paths

- Evidence policy: `effective_evidence_resolution` vs published `registry_metadata.evidence_resolution`.
- Workflow reference: decision-record fallbacks vs optional registry `client_workflow_class`.
- Score drivers vs workflow execution semantics (`EXECUTION_SEMANTICS_METADATA`) — not yet unified.

## Noncanonical Requirement Rendering Risks

- Surfaces allowing noncanonical rows in registry: reports_exports.
- CI guard: `governance_validation_engine.validate_noncanonical_requirement_ids` for synthetic IDs on governed rows.
