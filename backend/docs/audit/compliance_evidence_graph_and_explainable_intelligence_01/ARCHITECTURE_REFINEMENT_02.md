# Architecture Refinement Summary — Phase 2

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement ID:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Status:** Approved — supersedes Phase 2 scope in `PHASED_IMPLEMENTATION_PLAN.md` (Phase 2 section only)  
**Date:** 2026-06-02  
**Prerequisite:** Phase 1 complete (`ae1d8ae1` on `develop`); Refinement-01 approved

---

## What changed

Phase 2 Authority Integration is **approved in principle**. Refinement-02 strengthens long-term graph integrity without altering the observer-only authority model established in Refinement-01.

| # | Requirement | Architectural response |
|---|-------------|------------------------|
| 1 | Decision Quality metadata | `decision_quality` block on every decision + snapshot mirror; descriptive only |
| 2 | Compliance Graph Health | `compliance_graph_health_service` — operational subsystem metrics |
| 3 | Rule lineage | Full legislative hierarchy modelled as nodes + `derived_from` / `governed_by` edges |
| 4 | Graph Integrity Validator | Shared validator reused by health, staging acceptance, future scheduled checks |
| 5 | Runtime explainability validation | Graph Service methods exercised in Phase 2 acceptance (no AI) |
| 6 | Mutation coverage thresholds | P0 100%, P1 100%, P2 ≥95%; deferred rows require explicit justification |
| 7 | Incremental delivery | 2A→2E independently deployable and validated stages |
| 8 | Historical backfill | Bounded, idempotent `backfill_service.py` in Phase 2 |
| 9 | Future readiness | Capability mapping preserved; no redesign for Phase 3–8 consumers |
| 10 | Additional acceptance criteria | See § Acceptance criteria below |

**Unchanged:** Compliance Engine, Rules Engine, Jurisdiction Engine, Scoring Engine, and all authority services remain sole decision-makers. The graph observes only.

---

## Updated Phase 2 component map

```
backend/services/compliance_evidence_graph/
  producers/                    # 2B–2D — authority observers
    registry.py
    _base.py
    authority_sync.py | score.py | risk.py | evidence.py | …
  bridge_operational.py         # 2A — OE correlation bridge
  backfill_service.py           # 2D — bounded historical backfill
  validation/
    integrity_validator.py    # 2A — shared validation core
    checks/                     # per-check modules

backend/services/compliance_graph_health/
  service.py                    # 2A — health metrics + reports
  metrics.py

backend/services/compliance_graph_service/
  service.py                    # existing — exercised in 2E acceptance

backend/routes/
  compliance_graph.py           # existing Graph Service routes
  compliance_graph_health.py    # 2A — admin health endpoints (new)
```

---

## 1. Decision Quality metadata

Every `compliance_decision` and its paired snapshot carry a **`decision_quality`** object.

**Purpose:** Describe decision confidence and completeness for future Compliance Intelligence. **Must never modify compliance outcomes.**

See `COMPLIANCE_DECISION_MODEL.md` § Decision Quality.

Producers compute `decision_quality` from authoritative post-write state only (evidence authority blob, review events, rules evaluation output). Missing data yields explicit `unknown` / `insufficient` labels — never inferred upgrades.

---

## 2. Compliance Graph Health

The graph is an **operational subsystem** with measurable integrity.

**Service:** `compliance_graph_health_service`  
**Document:** `GRAPH_HEALTH_SERVICE.md`

Initial exposure: admin-only HTTP routes. Future integration: Automation Control Centre, System Health dashboards.

Health reports aggregate validator output into dashboard-ready metrics (counts, rates, severity tiers).

---

## 3. Rule lineage

Relationships extend beyond individual rule versions to preserve **why every rule exists and where it originated**.

**Document:** `RULE_LINEAGE_MODEL.md`

Hierarchy (top → bottom):

```
Legislation → Statutory Instrument → Government Guidance → Knowledge Centre Article
  → Policy Registry → Jurisdiction Rule → Local Authority Rule → Compliance Rule
  → Decision → Evidence → Outcome
```

Phase 2 producers emit lineage nodes and edges when authoritative sources provide refs. Backfill populates representative historical lineage at reduced confidence.

---

## 4. Graph Integrity Validator

**Component:** `compliance_evidence_graph/validation/integrity_validator.py`  
**Document:** `GRAPH_INTEGRITY_VALIDATOR.md`

Single validation core consumed by:

- Graph Health service (continuous / on-demand)
- Phase 2 staging acceptance scripts
- Future scheduled health checks (Phase 7+ Automation Control Centre)

Methods: `validate_graph`, `validate_decision`, `validate_snapshot`, `validate_relationships`, `validate_rule_lineage`, `validate_operational_links`, `validate_supersession`, `validate_tenant_isolation`.

---

## 5. Runtime explainability validation (Phase 2)

Phase 2 acceptance **must** invoke Graph Service methods directly against staging shadow data:

| Method | Acceptance proof |
|--------|------------------|
| `explain_decision` | Structured evidence from snapshot + graph only |
| `replay_decision` | Deterministic phase reconstruction |
| `trace_evidence` | Anchor → decision chain (graph walk where populated) |
| `compare_decision` | Deterministic diff between two decisions |
| `find_historical_decision` | `as_of` resolution from immutable records |
| `trace_operational_impact` | OE correlation join via `operational_correlation_id` |

No AI. Proves graph usability for Phase 3 Explainable Decision Engine without architectural change.

Script: `tmp_compliance_evidence_graph_phase2_acceptance.py` (2E deliverable).

---

## 6. Mutation coverage requirements

**Document:** `MUTATION_COVERAGE_MATRIX.md`

| Tier | Coverage required | Notes |
|------|-------------------|-------|
| **P0** | 100% | Closed-loop compliance spine |
| **P1** | 100% | Applicability, risk, extraction, materialization |
| **P2** | ≥95% | Reminders, notifications, work orders, reports, digests |

Any deferred mutation requires: reason, impact assessment, implementation plan, expected delivery phase. **No silent omissions.**

---

## 7. Delivery strategy (2A → 2E)

Each stage: implement → validate → commit → deploy to staging → sign-off gate before next stage.

| Stage | Scope | Validation gate |
|-------|-------|-----------------|
| **2A** | Infrastructure: registry skeleton, bridge, validator, health service, decision_quality schema | Unit tests + health/validator smoke on fixtures |
| **2B** | P0 producers + `decision_id` on core artefacts | P0 matrix 100%; idempotency; explain/replay smoke |
| **2C** | P1 producers + rule lineage emit + evidence nodes | P1 matrix 100%; lineage validator pass |
| **2D** | P2 producers + backfill service + operational artefact links | P2 ≥95%; backfill idempotency; historical explain |
| **2E** | Full acceptance: failure injection, performance, regression, staging report | All Refinement-02 acceptance criteria |

Feature flag remains `disabled` in production until Phase 2E staging acceptance complete. Staging uses `shadow` from 2B onward.

---

## 8. Historical backfill

**Component:** `backfill_service.py`

Objectives:

- Populate representative historical decisions and relationships
- Populate operational links where correlation exists in authoritative sources
- Enable realistic replay, comparison, and `explain_decision` validation

Constraints:

- Append-only — never overwrite existing evidence
- Idempotent — repeated execution safe
- `metadata.backfill=true`, reduced `decision_quality` confidence labels
- Bounded scope (configurable: tenant, date range, max decisions per run)

Delivered in **2D**; validated in **2E**.

---

## 9. Future readiness

Phase 2 data model and services prepare for (no redesign required):

| Future capability | Phase 2 preparation |
|-------------------|---------------------|
| Decision Diff | `compare_decision` + snapshot hashes |
| Portfolio Intelligence | Scoped decision listing + `decision_quality` aggregation |
| Compliance Advisor | Graph Service envelopes + quality metadata |
| Scenario Simulation | Immutable snapshots + supersession chains |
| Predictive Compliance | Historical decision sequences + rule lineage |
| Regulatory Impact Analysis | Full rule lineage graph |
| Audit Preparation | Validator + health + replay |
| Insurance Evidence | Evidence lineage + decision_quality |
| Natural Language Search | Structured envelopes (Phase 5 AI consumes these) |
| Root Cause Analysis | `trace_operational_impact` + supersession chain |

---

## Document index (Refinement-02 additions)

| Document | Content |
|----------|---------|
| `ARCHITECTURE_REFINEMENT_02.md` | This document |
| `PRODUCER_ARCHITECTURE.md` | Producer registry, hooks, idempotency |
| `MUTATION_COVERAGE_MATRIX.md` | P0/P1/P2 coverage with deferral registry |
| `RULE_LINEAGE_MODEL.md` | Legislative hierarchy nodes and edges |
| `GRAPH_HEALTH_SERVICE.md` | Health metrics and admin API |
| `GRAPH_INTEGRITY_VALIDATOR.md` | Validation checks and acceptance integration |
| `COMPLIANCE_DECISION_MODEL.md` | Updated — § Decision Quality |
| `GRAPH_DATA_MODEL.md` | Updated — rule lineage node/edge types |
| `PHASED_IMPLEMENTATION_PLAN.md` | Updated — Phase 2 sub-stages 2A–2E |

---

## Acceptance criteria (Refinement-02)

Phase 2 is complete only when **runtime evidence** proves:

- [ ] **Decision Quality** metadata exists on every emitted decision
- [ ] **Graph Health** reports no structural integrity failures at staging acceptance
- [ ] **Rule lineage** fully traceable for P0/P1 decision paths
- [ ] **Graph Integrity Validator** passes full suite on staging shadow data
- [ ] **Graph Service methods** reconstruct historical decisions without AI
- [ ] **Mutation Coverage Matrix** meets P0 100%, P1 100%, P2 ≥95%
- [ ] **Historical backfill** produces reproducible decision histories (idempotent re-run)
- [ ] **Incremental delivery** — each 2A–2E stage independently validated on staging
- [ ] **No compliance behaviour regression** with `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled`
- [ ] **Observer-only** — graph never influences authoritative outcomes
- [ ] **Phase 3 ready** — Explainable Decision Engine requires no architectural redesign

---

## Approval status

| Item | Status |
|------|--------|
| Phase 2 Authority Integration (principle) | **Approved** |
| Refinement-02 architecture | **Approved** |
| Phase 2A implementation | **Authorised** — proceed on `develop` after this doc merge |
| Production | Untouched; flag `disabled` until 2E staging acceptance |
