# Graph Integrity Validator

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Phase:** 2A (infrastructure)

---

## Purpose

Dedicated validation component ensuring Compliance Evidence Graph structural integrity. Single implementation reused by:

1. Graph Health service (on-demand and future scheduled)
2. Phase 2 staging acceptance scripts
3. Future Automation Control Centre health jobs

The validator is **read-only**. It never repairs or mutates graph data.

---

## Component location

```
backend/services/compliance_evidence_graph/validation/
  __init__.py
  integrity_validator.py    # public API
  checks/
    decisions.py
    snapshots.py
    relationships.py
    rule_lineage.py
    operational_links.py
    supersession.py
    tenant_isolation.py
    graph_wide.py
  result.py                 # ValidationResult, CheckFailure dataclasses
```

---

## Public API

```python
async def validate_graph(
    *,
    client_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    max_decisions: int = 10_000,
) -> ValidationResult: ...

async def validate_decision(decision_id: str) -> ValidationResult: ...

async def validate_snapshot(snapshot_id: str) -> ValidationResult: ...

async def validate_relationships(*, decision_id: str | None = None) -> ValidationResult: ...

async def validate_rule_lineage(*, decision_id: str) -> ValidationResult: ...

async def validate_operational_links(*, decision_id: str) -> ValidationResult: ...

async def validate_supersession(*, decision_id: str | None = None) -> ValidationResult: ...

async def validate_tenant_isolation(
    *,
    client_id: str | None = None,
) -> ValidationResult: ...
```

`validate_graph()` orchestrates all checks. Individual methods support targeted debugging.

---

## Check catalogue

### `validate_decision`

| Rule | Severity |
|------|----------|
| `decision_id` unique | failure |
| `dedupe_key` unique | failure |
| `snapshot_id` present and resolvable | failure |
| `decision_type` in allowed enum | failure |
| `client_id` present for tenant-scoped decisions | failure |
| `decision_quality` block present (runtime; backfill may mark `inferred`) | failure |
| `decision_authority` complete | failure |
| `source.collection` + `source.id` present | failure |

### `validate_snapshot`

| Rule | Severity |
|------|----------|
| Exactly one snapshot per `decision_id` | failure |
| `snapshot_hash` matches canonical payload | failure |
| `decision_quality` mirror consistent with decision | warning |
| Required sections for `decision_type` (configurable matrix) | warning |

### `validate_relationships`

| Rule | Severity |
|------|----------|
| All edges: `from_node_id` and `to_node_id` resolve | failure |
| All edges: full provenance block | failure |
| `edge_type` in allowed enum | failure |
| Active edges: no duplicate `(from, to, edge_type)` for authoritative strength | failure |
| Decision-linked edges reference valid `provenance.decision_id` | failure |

### `validate_rule_lineage`

| Rule | Severity |
|------|----------|
| Governed decisions have `decided_under` → rule node | warning (P0: failure at 2E) |
| Rule node chain reaches legislation or explicit `lineage_incomplete` flag | warning |
| No cycles in `derived_from` except documented exceptions | failure |
| Lineage edge provenance complete | failure |

### `validate_operational_links`

| Rule | Severity |
|------|----------|
| When `operational_correlation_id` set, OE event or queue record exists | warning |
| `correlates_with` edges align with correlation ID | warning |
| Snapshot `operational_context` fields consistent with decision | warning |

### `validate_supersession`

| Rule | Severity |
|------|----------|
| `previous_decision_id` → target exists | failure |
| Bidirectional consistency: A.superseding ↔ B.previous | failure |
| No supersession cycles | failure |
| Superseded edges have `is_active: false` + replacement | warning |

### `validate_tenant_isolation`

| Rule | Severity |
|------|----------|
| Decision `client_id` matches all linked nodes | failure |
| Decision `client_id` matches snapshot | failure |
| Edge endpoints share tenant scope | failure |
| Cross-tenant `correlates_with` forbidden | failure |

### `validate_graph` (aggregate)

Runs all checks over scoped decision set. Reports counts and samples for each failure class.

---

## ValidationResult schema

```json
{
  "valid": true,
  "checks_run": 8,
  "failures": [],
  "warnings": [],
  "stats": {
    "decisions_examined": 100,
    "snapshots_examined": 100,
    "nodes_examined": 450,
    "edges_examined": 620
  },
  "duration_ms": 842
}
```

Each failure entry:

```json
{
  "check": "validate_tenant_isolation",
  "severity": "failure",
  "entity_type": "edge",
  "entity_id": "ceg_edge_xyz",
  "decision_id": "dec_abc",
  "message": "from_node client_id mismatch",
  "details": { "expected_client_id": "c1", "actual_client_id": "c2" }
}
```

---

## Staging acceptance integration

Phase 2E acceptance script must:

1. Run `validate_graph()` after full compliance journey
2. Assert `valid: true` OR document approved warnings with remediation plan
3. Run failure-injection scenarios and re-validate (no duplicate nodes/edges/decisions)
4. Store result in `PHASE_2_INTEGRITY_VALIDATION.json`

Regression: validator tests in `tests/test_graph_integrity_validator.py` (2A deliverable).

---

## Future scheduled checks

Same validator, invoked by:

- Cron job (weekly staging, daily production when enabled)
- Post-deploy smoke hook
- Automation Control Centre manual trigger

No separate validation logic — health service wraps this component only.
