# Phase 2C Implementation — P1 Producers

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Stage:** 2C — P1 applicability, risk, extraction, materialization (100% coverage target)  
**Predecessor:** Phase 2B (`7940bfe0` on `develop`)

---

## Summary

Phase 2C adds **11 P1 producer handlers** plus **rule lineage** on all emits. Review subtypes P1-08–P1-13 remain covered via the existing P0 `evidence_review_transition` hook with `p1_transition_category` metadata in snapshots.

All dispatch via `dispatch_p1_producer()` / `dispatch_producer()` → Producer Registry. Observer-only; failures never block authority.

---

## P1 producer modules

| Module | Mutation kinds |
|--------|----------------|
| `applicability.py` | `applicability_operator`, `requirement_materialization`, `property_jurisdiction_materialization`, `registry_publish` |
| `risk.py` | `risk_signal_generation`, `risk_signal_regen_worker` |
| `document.py` | `document_extraction_apply`, `document_extraction_reject` |
| `evidence.py` | `cer_linkage`, `supporting_document_linkage` |
| `score.py` | `admin_score_repair` (extends 2B) |
| `lineage.py` + `_emit.py` | Rule lineage on all P0/P1 emits (P1-16) |

---

## Instrumentation hooks (12 direct sites)

| Writer | Hook |
|--------|------|
| `execute_applicability_operator_command` | P1-01 |
| `patch_property` → materialize | P1-02 + P1-03 |
| `materialize_requirements_for_property` | P1-03 |
| `generate_risk_signals_for_property` | P1-04 |
| `run_risk_signal_regen_worker` | P1-05 |
| `apply_ai_extraction` | P1-06 |
| `reject_ai_extraction` | P1-07 |
| `append_evidence_review_event` | P1-08–13 via P0 review producer |
| `create_compliance_evidence_record` / `upsert_document_upload_evidence_for_linked_document` | P1-10 |
| `reconcile_document_linkage` (supporting-only) | P1-11 |
| `recalculate_and_persist` when `REASON_ADMIN_VALIDATOR_REPAIR` | P1-14 |
| `publish_publish_queue_item` | P1-15 |

---

## Validation

- Unit tests: `tests/test_ceg_producers_p1.py`
- Local runtime: `tmp_compliance_evidence_graph_phase2c_validation.py`
- Staging shadow validation: pending (same pattern as Phase 2B)

---

## Feature flag

Unchanged: `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled|shadow|enabled` (default `disabled`).
