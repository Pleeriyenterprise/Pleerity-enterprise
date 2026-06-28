# Phased Implementation Plan (Refined)

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01

---

## Overview

Delivery model: **Decision + Snapshot foundation → Graph Service Layer → Producers → Consumer migration → AI (last)**.

The graph is a **shared platform capability**, not an AI feature. Graph storage is never exposed directly.

**Estimated phases:** 0–9.

---

## Phase 0 — Architecture ✓

**Deliverables:**
- `COMPLIANCE_EVIDENCE_GRAPH_ARCHITECTURE.md` (refined)
- `COMPLIANCE_DECISION_MODEL.md`
- `GRAPH_SERVICE_LAYER.md`
- `GRAPH_DATA_MODEL.md` (refined)
- `AI_INTELLIGENCE_LAYER_ARCHITECTURE.md` (refined)
- `ARCHITECTURE_REFINEMENT_01.md`
- `PHASED_IMPLEMENTATION_PLAN.md` (this document)

**Exit criteria:** Refinement-01 approved.

---

## Phase 1 — Decision foundation + Graph Service Layer

**Scope:**
- Collections: `compliance_decisions`, `compliance_decision_snapshots`, `compliance_evidence_nodes`, `compliance_evidence_edges`
- Indexes in `database.py`
- `services/compliance_evidence_graph/` — internal `emit_service` (atomic decision + snapshot + nodes + provenanced edges)
- `services/compliance_graph_service/` — all method signatures; implement:
  - `explain_decision()`
  - `find_historical_decision()`
  - `compare_decision()`
  - `compare_decision_snapshots()` (stub returns structured empty diff when insufficient data)
- HTTP routes: `/api/compliance/graph/*` only — **no raw storage API**
- Tests: decision immutability, snapshot 1:1, edge provenance required, access boundary (no external storage imports)
- Feature flag: `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled`

**Not in Phase 1:** LLM, producers at mutation sites, customer routes, UI.

**Exit criteria:** Can emit/query decisions via Graph Service; historical lookup by `as_of` works on seeded test data; access boundary tests pass.

---

## Phase 2 — Runtime producers, integrity & OE bridge (Refinement-02)

**Refinement:** `ARCHITECTURE_REFINEMENT_02.md`  
**Delivery:** Incremental sub-stages 2A → 2E (each independently deployable and validated)

### 2A — Infrastructure

- Producer registry skeleton + `_base.py` (dedupe, provenance, `decision_quality` computation)
- `bridge_operational.py` — OE correlation enrichment
- `validation/integrity_validator.py` — shared validation core
- `compliance_graph_health/` — health service + admin routes
- `decision_quality` schema on decisions/snapshots
- Unit tests: validator, health, registry gating
- **Gate:** validator + health smoke on fixtures; commit; deploy staging

### 2B — P0 primary authority producers

- Wire P0 hooks: authority sync, scoring, review, outcome engine
- `decision_id` on `score_ledger_events`, `compliance_activity_log`, `evidence_review_events`
- P0 mutation matrix → 100% implemented
- Runtime: explain/replay smoke; idempotency tests
- Staging: `COMPLIANCE_EVIDENCE_GRAPH_MODE=shadow`
- **Gate:** P0 validated; commit; deploy staging

### 2C — P1 secondary producers

- Applicability, materialization, risk, document extraction, CER/linkage
- Rule lineage nodes + edges (`RULE_LINEAGE_MODEL.md`)
- Evidence graph vertices (document, CER, requirement)
- P1 mutation matrix → 100% validated
- **Gate:** lineage validator pass; commit; deploy staging

### 2D — P2 operational artefacts + backfill

- Reminders, notifications, work orders, reports, knowledge refs
- `backfill_service.py` — bounded, idempotent historical decisions
- P2 mutation matrix → ≥95% validated (deferrals documented)
- **Gate:** backfill idempotency; historical explain; commit; deploy staging

### 2E — Acceptance validation

- Full compliance journeys (onboarding → report)
- Graph Service direct validation: explain, replay, trace, compare, historical, operational impact
- Failure injection: retry, duplicate, worker restart, queue replay
- Graph Integrity Validator full suite
- Graph Health report (no structural failures)
- Performance assessment (emit/producer latency)
- Regression gate (`disabled` mode unchanged behaviour)
- Deliverables: `PHASE_2_STAGING_READINESS.json`, coverage + integrity validation JSON

**Scope summary:**

| Component | Stage |
|-----------|-------|
| `producers/` at mutation authorities | 2B–2D |
| Decision Quality metadata | 2A emit, enforced 2B+ |
| Graph Health service | 2A |
| Graph Integrity Validator | 2A |
| Rule lineage model | 2C |
| Operational bridge | 2A–2B |
| Historical backfill | 2D |
| Downstream `decision_id` propagation | 2B–2D |
| Mutation coverage matrix | 2B–2E |

**Exit criteria (Refinement-02):**

- Decision Quality on every decision
- Graph Health + Validator pass on staging shadow data
- Rule lineage traceable for P0/P1 paths
- Graph Service reconstructs history without AI
- P0 100%, P1 100%, P2 ≥95% coverage (deferrals registered)
- Backfill idempotent and reproducible
- Each 2A–2E stage independently validated on staging
- No compliance regression with flag `disabled`
- Phase 3 ready without redesign

---

## Phase 3 — Full Graph Service + trace/compare

**Scope:**
- Implement remaining Graph Service methods:
  - `replay_decision()`, `trace_evidence()`, `trace_requirement()`
  - `find_decision_dependencies()`, `find_affected_*()`, `find_missing_evidence()`, `find_superseded_evidence()`
  - `trace_operational_impact()`
- Deterministic response envelopes with full AI-ready metadata
- Admin + client HTTP routes for all methods
- Consumer adapter: Compliance Engine read path uses Graph Service

**No LLM.**

**Exit criteria:** All Graph Service methods return structured responses; `compare_decision` produces deterministic diffs; historical questions use snapshots.

---

## Phase 4 — Explain This UI & Compliance Replay (Graph Service consumers)

**Scope:**
- `ExplainThisPanel.js` — calls `explain_decision` / object-scoped explain wrappers
- Compliance Replay drawer — calls `replay_decision`
- Decision Diff UI — calls `compare_decision`
- Admin decision explorer (read-only, Graph Service only)
- Migrate `compliance_explain_admin_service` to Graph Service when `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled`

**Exit criteria:** Admin can explain/replay/compare decisions from UI; no direct storage queries from frontend.

---

## Phase 5 — AI Intelligence Layer (Graph Service consumer only)

**Scope:**
- `services/compliance_intelligence/` — all services consume Graph Service envelopes only
- Citation-required LLM schema + post-validator
- `compliance_ai_narrations` audit collection
- Admin `POST /investigate` dispatches to Graph Service then optional narration
- **Lint enforcement:** no `compliance_evidence_graph.storage` imports in intelligence package

**Exit criteria:** AI answers reproducible from Graph Service response hashes; uncited claims stripped.

---

## Phase 6 — Regulatory explainability & rule explanation

**Scope:**
- Legislation version attachment on decisions/snapshots
- `regulation_interpreter` via Graph Service
- Regulator evidence pack export (snapshot bundle)
- Rule explanation: exemptions, exclusions, decision path in snapshot `decision_reasoning_inputs`

---

## Phase 7 — Multi-consumer surfaces

**Scope:**
- Customer Portal — filtered `explain_decision` (role-scoped)
- Inspector / Auditor journey — `replay_decision` + `trace_requirement`
- Reporting — report jobs cite `decision_id`; historical reports use snapshots
- Knowledge Centre — legislation links to decision nodes
- OE Timeline — deep links to `explain_decision` via `trace_operational_impact`

**Exit criteria:** Tenant isolation verified; inspector journey matches admin replay.

---

## Phase 8 — Advanced intelligence (read-only)

**Scope:**
- Portfolio / predictive / scenario intelligence (Graph Service composition)
- Performance: lazy load, cache, maintenance job
- Scenario dry-run uses `compare_decision` on hypothetical branch — no writes

---

## Phase 9 — Staging acceptance & promotion gate

**Scope:**
- Full acceptance validation (Refinement-01 criteria)
- E2E: every explanation from Graph Service; historical replay from snapshots
- Regression: scoring, workflows, OE platform
- Production promotion checklist

---

## Phase 1 implementation layout (authorised)

```
backend/services/compliance_evidence_graph/
  __init__.py
  constants.py
  context.py
  emit_service.py
  storage/
    __init__.py
    decisions.py
    snapshots.py
    nodes.py
    edges.py
backend/services/compliance_graph_service/
  __init__.py
  service.py          # explain_decision, find_historical, compare_*
  envelopes.py        # AI-ready response shapes
  access.py             # tenant/role guards
backend/routes/compliance_graph.py
backend/tests/test_compliance_graph_service.py
backend/tests/test_graph_service_access_boundary.py
backend/database.py     # indexes only
```

**Estimate:** ~1,200–1,800 LOC backend.

---

## Migration strategy

| Existing | Migration |
|----------|-----------|
| `explanation_engine.py` | Keep for risk; add Graph Service delegation when decision exists |
| `compliance_explain_admin_service.py` | Phase 4: Graph Service when flag enabled |
| `compliance_timeline.py` | Phase 8: optional projection from decisions |
| Client score explanation | Phase 7: `explain_decision` on latest score change decision |

Feature flag: `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled|shadow|enabled`

---

## Approval status

| Item | Status |
|------|--------|
| Refinement-01 architecture | **Approved** |
| Phase 1 implementation | **Complete** — `ae1d8ae1` on `develop` |
| Refinement-02 architecture | **Approved** |
| Phase 2A implementation | **Authorised** — proceed on `develop` |
| Production | Untouched until Phase 2E staging acceptance; flag `disabled` |
