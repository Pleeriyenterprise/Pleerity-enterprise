# Phase 3 Implementation — Full Graph Service + Trace/Compare

**Stage:** 3 — Graph Service methods, HTTP routes, consumer adapter  
**Predecessor:** Phase 2E (`f8207336` on `develop`)

## Summary

- **Graph Service methods** — `replay_decision`, `trace_evidence`, `trace_requirement`, `find_decision_dependencies`, `find_affected_properties`, `find_affected_requirements`, `find_missing_evidence`, `find_superseded_evidence`, `trace_operational_impact`, `list_decisions`
- **Deterministic envelopes** — `insufficient()` sets `status: "insufficient"` for AI-ready metadata
- **Admin + tenant HTTP routes** — `routes/compliance_graph.py` exposes all methods; no raw storage API
- **Consumer adapter** — `services/compliance_graph_service/consumer_adapter.py` for object-scoped explain and admin KPI enrichment
- **Feature flags** — `graph_admin_consumers_enabled()` (shadow|enabled), `graph_consumers_enabled()` (enabled only)

## Deliverables

| Artifact | Path |
|----------|------|
| Graph Service | `services/compliance_graph_service/service.py` |
| Consumer adapter | `services/compliance_graph_service/consumer_adapter.py` |
| Config flags | `services/compliance_evidence_graph/config.py` |
| HTTP routes | `routes/compliance_graph.py` |
| Health bootstrap | `routes/compliance_graph_health.py` (producer registry init) |
| Unit tests | `tests/test_compliance_graph_service_phase3.py` |

## Validation

- Unit tests: `tests/test_compliance_graph_service_phase3.py`, `tests/test_compliance_graph_service.py`, `tests/test_compliance_graph_health.py` (14 passed locally)
- Staging: `COMPLIANCE_EVIDENCE_GRAPH_MODE=shadow` — admin routes callable; consumers gated by flag

## Exit criteria (plan)

- All Graph Service methods return structured responses ✓
- `compare_decision` produces deterministic diffs ✓ (Phase 1 + unchanged)
- Historical questions use snapshots ✓
- No LLM ✓
