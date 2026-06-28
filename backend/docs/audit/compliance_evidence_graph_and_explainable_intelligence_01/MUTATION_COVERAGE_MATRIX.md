# Mutation Coverage Matrix — Phase 2

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Companion:** `docs/STREAM_E_MUTATION_FANOUT_MATRIX.md` (authoritative mutation inventory)

---

## Coverage thresholds (acceptance)

| Tier | Required coverage | Phase 2 stage |
|------|-------------------|---------------|
| **P0** | **100%** | 2B |
| **P1** | **100%** | 2C |
| **P2** | **≥95%** | 2D |

Any row not meeting threshold at acceptance requires an entry in **Deferral Registry** (§ below). No silent omissions.

---

## Status legend

| Status | Meaning |
|--------|---------|
| `planned` | Producer designed; not implemented |
| `implemented` | Producer wired; pending validation |
| `validated` | Runtime evidence on staging shadow |
| `deferred` | Explicitly deferred with registry entry |

---

## P0 — Closed-loop compliance spine (100% required)

| ID | Mutation | Authoritative writer | Producer | Stream E row | Hook | Status |
|----|----------|---------------------|----------|--------------|------|--------|
| P0-01 | Evidence authority sync | `sync_requirement_evidence_authority` | `authority_sync.py` | 9 | ✓ | validated |
| P0-02 | Compliance score recalc | `recalculate_and_persist` | `score.py` | — | ✓ | validated |
| P0-03 | Score ledger write | `log_score_change` | `score.py` | — | ✓ | validated |
| P0-04 | Evidence review transition | `append_evidence_review_event` | `review.py` | 6–8 | ✓ | validated |
| P0-05 | Document verify (admin) | `evidence_review_verify` / `documents.py` | `review.py` | 6–7 | via P0-04 | implemented |
| P0-06 | Document reject | `documents.py` reject paths | `review.py` | 8 | via P0-04 | implemented |
| P0-07 | Outcome engine events | `apply_action_outcome` | `outcome.py` | Appendix | ✓ | validated |
| P0-08 | Recalc queue enqueue | `enqueue_compliance_recalc` | — | — | deferred 2B | deferred |
| P0-09 | Recalc worker completion | worker → P0-02 | `score.py` | — | via P0-02 | validated |
| P0-10 | Document upload (linked) | upload → authority sync | `authority_sync.py` | 1, 3–4 | via P0-01 | implemented |
| P0-11 | Document delete (linked) | delete → authority sync | `authority_sync.py` | 5 | via P0-01 | implemented |
| P0-12 | Requirement PATCH | `patch_requirement` | `authority_sync.py` | 10 | via P0-01 | implemented |
| P0-13 | Mark N/A / reopen workflow | `api_compliance_workflow.py` | `authority_sync.py` | 21–22 | via P0-01 | implemented |
| P0-14 | Certificate verified outcome | `apply_action_outcome` | `outcome.py` | Appendix | via P0-07 | validated |
| P0-15 | Requirement completed outcome | `apply_action_outcome` | `outcome.py` | Appendix | via P0-07 | validated |

**P0 producer hooks (Phase 2B):** 5 direct instrumentation points cover all 15 rows (queue enqueue P0-08 deferred — operational link only, no decision authority).

**P0 count:** 15 rows — **14/15 implemented; 1 deferred (P0-08 queue enqueue metadata-only)**

---

## P1 — Applicability, risk, extraction, materialization (100% required)

| ID | Mutation | Authoritative writer | Producer | Stream E row | Status |
|----|----------|---------------------|----------|--------------|--------|
| P1-01 | Applicability operator | `execute_applicability_operator_command` | `applicability.py` | 12 | planned |
| P1-02 | Property jurisdiction PATCH | `patch_property` → materialize | `applicability.py` | 11 | planned |
| P1-03 | Requirement materialization | `materialize_requirements_for_property` | `applicability.py` | 11 | planned |
| P1-04 | Risk signal generation | `generate_risk_signals_for_property` | `risk.py` | — | planned |
| P1-05 | Risk regen worker | `run_risk_signal_regen_worker` | `risk.py` | — | planned |
| P1-06 | AI extraction apply | `apply-extraction` / evidence review AI | `document.py` | — | planned |
| P1-07 | Extraction reject | reject-extraction paths | `document.py` | — | planned |
| P1-08 | Human review complete | evidence review state transitions | `review.py` | — | planned |
| P1-09 | External verification record | evidence review verify-external | `review.py` | — | planned |
| P1-10 | CER write / linkage | `compliance_evidence_record_service` | `evidence.py` | — | planned |
| P1-11 | Supporting document linkage | `supporting_evidence_linkage` | `evidence.py` | — | planned |
| P1-12 | Evidence mark expired | evidence review mark-expired | `review.py` | — | planned |
| P1-13 | Evidence supersede | evidence review supersede | `review.py` | — | planned |
| P1-14 | Admin score repair | `validate_compliance_score` fix=true | `score.py` | 19 | planned |
| P1-15 | Registry publish downstream | `compliance_registry_publish_service` | `applicability.py` | — | planned |
| P1-16 | Rule lineage emit | all P0/P1 producers | `_base` + lineage | — | planned |

**P1 count:** 16 rows — **target validated: 16/16**

---

## P2 — Operational artefacts (≥95% required)

| ID | Mutation | Authoritative writer | Producer | Stream E row | Status |
|----|----------|---------------------|----------|--------------|--------|
| P2-01 | Daily reminders | `send_daily_reminders` | `reminder.py` | — | planned |
| P2-02 | Reminder cancelled | reminder cancel paths | `reminder.py` | — | planned |
| P2-03 | Monthly digest | `send_monthly_digests` | `reminder.py` | — | planned |
| P2-04 | Notification queued | `notification_orchestrator` | `notification.py` | — | planned |
| P2-05 | Notification sent | orchestrator send success | `notification.py` | — | planned |
| P2-06 | Work order create | `create_work_order` | `work_order.py` | — | planned |
| P2-07 | Work order complete | `update_work_order` COMPLETED | `work_order.py` | 17 | planned |
| P2-08 | Issue created/resolved | `maintenance_issues_service` | `outcome.py` | 18 | planned |
| P2-09 | Compliance status alert | `check_compliance_status_changes` | `notification.py` | — | planned |
| P2-10 | Report generation | report jobs | `score.py` / dedicated | — | planned |
| P2-11 | Portfolio recalc | org-level scoring paths | `score.py` | — | planned |
| P2-12 | Knowledge reference attach | KC linkage paths | `knowledge.py` | — | planned |
| P2-13 | Tenant delivery proof | `tenant_delivery_proof_service` | `authority_sync.py` | 13–14 | planned |
| P2-14 | Webhook fan-out | `webhook_service.fire_*` | link only (decision_id in metadata) | — | planned |
| P2-15 | WO SLA / schedule reminders | `job_runner` WO jobs | `work_order.py` | — | planned |
| P2-16 | Risk signal ack/resolve | `risk_signal_service` | `outcome.py` | — | planned |
| P2-17 | Admin bulk recalc enqueue | `admin_action_recalculate_compliance` | operational link | 20 | planned |
| P2-18 | Gap backfill batch | `compliance_gap_backfill.py` | deferred — see registry | 15 | planned |
| P2-19 | Policy gap reconciliation | `compliance_policy_backfill_service` | deferred — see registry | 16 | planned |
| P2-20 | Operational incident bridge | OE incident affecting compliance | `operational_bridge.py` | — | planned |

**P2 count:** 20 rows — **minimum validated: 19/20 (95%)**

---

## Deferral registry

Rows marked `deferred` must include all four fields before Phase 2E acceptance.

| ID | Reason | Impact | Implementation plan | Expected phase |
|----|--------|--------|---------------------|----------------|
| P0-08 | Queue enqueue is scheduling only; decision occurs at recalc (P0-02) | Low — no separate compliance decision at enqueue | Optional OE correlation link only | Phase 2.5 |
| P2-18 | Batch gap backfill is ops tooling; not customer mutation path | Low — gaps refreshed by runtime sync elsewhere | Emit on `sync_compliance_gaps_for_requirement` when called from backfill with audit flag | Phase 2.5 or Phase 7 |
| P2-19 | Policy reconciliation patches inference only; not full authority sync | Low — no new compliance decisions | Observer on reconciliation checkpoint events | Phase 7 |

*Update this table when deferring any row. Empty deferral at 2E means 100%/100%/≥95% achieved.*

---

## Validation evidence

Each `validated` row must cite:

- Staging shadow run timestamp
- Sample `decision_id`(s)
- Dedupe key used
- Graph Service `explain_decision` success
- Validator pass for linked decision

Stored in: `PHASE_2_MUTATION_COVERAGE_VALIDATION.json` (2E deliverable).

---

## Change control

New authoritative mutation paths added after Phase 2 must:

1. Add a row to this matrix
2. Register `mutation_kind` in producer registry
3. Assign P0/P1/P2 priority
4. Not ship without producer or explicit deferral entry
