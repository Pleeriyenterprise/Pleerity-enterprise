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

## Phase 2 — Runtime producers & OE bridge

**Scope:**
- `producers.py` at mutation authorities (authority sync, scoring, review, CER, applicability)
- Each producer emits decision + snapshot atomically
- Downstream artefacts receive `decision_id` (`score_ledger_events`, etc.)
- `bridge_operational.py` — `operational_correlation_id` + OE metadata
- `backfill_service.py` — bounded historical decisions from authoritative sources (reduced confidence, `metadata.backfill=true`)
- Feature flag: `shadow` mode on staging

**Exit criteria:** New staging mutations create decisions; score ledger cites `decision_id`; OE cross-link works.

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
| Phase 1 implementation | **Authorised** — proceed on `develop` |
| Production | Untouched until Phase 9 gate |
