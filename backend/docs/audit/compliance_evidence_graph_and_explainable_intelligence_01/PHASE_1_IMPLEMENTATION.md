# Compliance Evidence Graph — Phase 1 Implementation

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Phase:** 1 — Decision foundation + Graph Service Layer  
**Implemented at:** 2026-06-28  
**Branch:** `develop` (local)  
**Feature flag:** `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled` (default); fixtures use `phase1_validation`

---

## Summary

Phase 1 delivers the immutable **Compliance Decision** + **Decision Snapshot** foundation, append-only graph nodes/edges with **full edge provenance**, an internal storage layer, and a public **Graph Service Layer** as the sole supported access path. No AI, no mutation producers, no raw storage API.

**Runtime validation:** `PHASE_1_RUNTIME_VALIDATION.json` — 7/7 checks passed — **PHASE_2_READY**

---

## Files changed / added

### Internal graph storage (`services/compliance_evidence_graph/`)

| File | Purpose |
|------|---------|
| `constants.py` | Collection names, decision/node/edge enums |
| `config.py` | Feature flag + emit guards |
| `emit_service.py` | Atomic decision + snapshot + nodes + provenanced edges |
| `storage/decisions.py` | Append-only decision queries |
| `storage/snapshots.py` | Immutable snapshot storage |
| `storage/nodes.py` | Append-only graph nodes |
| `storage/edges.py` | Append-only provenanced edges |

### Graph Service Layer (`services/compliance_graph_service/`)

| File | Purpose |
|------|---------|
| `service.py` | All public graph service methods |
| `envelopes.py` | AI-ready structured response envelopes |
| `access.py` | Tenant isolation guards |
| `fixtures.py` | Phase 1 controlled fixture emit |

### HTTP routes

| File | Purpose |
|------|---------|
| `routes/compliance_graph.py` | `/api/compliance/graph/*` + `/api/admin/compliance/graph/*` |

### Infrastructure

| File | Change |
|------|--------|
| `database.py` | Indexes for 4 new collections |
| `server.py` | Register `compliance_graph.router` |

### Tests

| File | Coverage |
|------|----------|
| `tests/test_compliance_evidence_graph.py` | Emit, idempotency, provenance, flag guards |
| `tests/test_compliance_graph_service.py` | Explain, replay, compare, historical, tenant isolation |
| `tests/test_graph_service_access_boundary.py` | No unauthorized storage imports |

### Validation

| File | Purpose |
|------|---------|
| `tmp_compliance_evidence_graph_phase1_validation.py` | Runtime fixture validation script |
| `docs/audit/.../PHASE_1_RUNTIME_VALIDATION.json` | Runtime evidence |

---

## Collections and indexes

| Collection | Role | Key indexes |
|------------|------|-------------|
| `compliance_decisions` | First-class immutable decisions | `decision_id`, `dedupe_key`, `client_id+decision_timestamp`, `property_id`, `requirement_id`, `snapshot_id` |
| `compliance_decision_snapshots` | Frozen knowledge at decision time | `snapshot_id`, `decision_id`, `snapshot_hash`, `client_id+snapshot_timestamp` |
| `compliance_evidence_nodes` | Graph traversal vertices | `node_id`, `dedupe_key`, `decision_id`, scoped query axes |
| `compliance_evidence_edges` | Provenanced relationships | `edge_id`, `dedupe_key`, `provenance.decision_id`, `provenance.is_active` |

**Immutability:** Storage modules expose `insert_*` and `get_*` only — no `update_one` / `replace_one`.

---

## Graph Service methods implemented

| Method | Status |
|--------|--------|
| `explain_decision` | ✓ Full |
| `replay_decision` | ✓ Full |
| `compare_decision` | ✓ Full |
| `compare_decision_snapshots` | ✓ Full |
| `find_historical_decision` | ✓ Full |
| `trace_evidence` | ✓ Basic |
| `trace_requirement` | ✓ Basic |
| `find_decision_dependencies` | ✓ Full |
| `find_affected_properties` | ✓ Full |
| `find_affected_requirements` | ✓ Full |
| `find_missing_evidence` | ✓ Snapshot-driven |
| `find_superseded_evidence` | ✓ Snapshot-driven |
| `trace_operational_impact` | ✓ Full |

All responses include AI-ready envelope fields (`authoritative_references`, lineage, confidence, legislation, historical/operational refs).

---

## API routes

### Admin (`/api/admin/compliance/graph/`)

- `GET /decisions/{id}/explain`
- `GET /decisions/{id}/replay`
- `GET /decisions/compare?left=&right=`
- `GET /snapshots/compare?left=&right=`
- `GET /historical?client_id=&as_of=`
- `GET /decisions/{id}/dependencies`
- `GET /decisions/{id}/operational-impact`
- `POST /fixtures/seed` (Phase 1 validation only)

### Tenant (`/api/compliance/graph/`)

- `GET /decisions/{id}/explain`
- `GET /decisions/{id}/replay`
- `GET /decisions/compare?left=&right=`
- `GET /historical?client_id=&as_of=`
- `GET /requirements/{id}/trace`
- `GET /evidence/trace`

**Not exposed:** Raw `GET /nodes`, `GET /subgraph` (debug returns 404 unless `COMPLIANCE_EVIDENCE_GRAPH_DEBUG=true`).

---

## Test results

```
tests/test_compliance_evidence_graph.py      4 passed
tests/test_compliance_graph_service.py       7 passed
tests/test_graph_service_access_boundary.py  3 passed
tests/test_operational_evidence_platform.py 10 passed (regression)
─────────────────────────────────────────────────────────
Total Phase 1 + regression:                  24 passed
```

---

## Security validation

| Check | Result |
|-------|--------|
| Admin routes require `admin_route_guard` | ✓ |
| Tenant routes require `require_auth` | ✓ |
| Cross-tenant access returns 403 | ✓ Tested |
| Graph storage not imported from routes (except graph service) | ✓ |
| Raw storage debug endpoint blocked by default | ✓ 404 |
| `COMPLIANCE_EVIDENCE_GRAPH_MODE=disabled` blocks live emit | ✓ |
| `graph_producers_enabled()` false when disabled | ✓ |

---

## Immutability validation

| Entity | Enforcement |
|--------|-------------|
| Decisions | `insert_one` only; idempotent via `dedupe_key` |
| Snapshots | `insert_one` only; content-addressed `snapshot_hash` |
| Nodes | Append-only |
| Edges | Append-only; `provenance.is_active` for supersession (no delete) |
| Supersession chain | Via `previous_decision_id` on new decision (no in-place updates) |

---

## Performance notes (staging Mongo, fixture run)

| Operation | Latency |
|-----------|---------|
| Fixture emit (2 decisions) | ~810ms |
| `explain_decision` | ~109ms |
| `replay_decision` | ~217ms |
| `compare_decision` | ~229ms |

Acceptable for Phase 1 foundation. Index-backed queries on `decision_id` / `client_id+timestamp`.

---

## Remaining risks

1. **No live producers** — graph empty in production until Phase 2 hooks authority sync / scoring.
2. **Trace methods** — basic implementation; deeper graph traversal in Phase 3.
3. **`find_missing_evidence` / `find_superseded_evidence`** — depend on snapshot fields populated by producers.
4. **Rent schedules index warning** on staging startup — pre-existing, unrelated to CEG.
5. **Customer-facing UI** — deferred to Phase 4+.

---

## Authority constraints honoured

- Compliance Engine, Rules Engine, Jurisdiction Engine, scoring services **unchanged**
- Graph **indexes** decisions; does not create or override compliance authority
- No scoring / rule / compliance engine code modified
- No production deployment
- Feature flag default `disabled` for live producers

---

## Recommendation

### **PHASE_2_READY**

Phase 1 acceptance criteria met. Proceed to Phase 2 (mutation producers at authority sync, scoring, review + `decision_id` on downstream artefacts) upon explicit approval.

**Do not proceed to Phase 2 without explicit approval.**
