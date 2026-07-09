# Compliance Graph Health Service

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIGENCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-PHASE-2-ARCHITECTURE-REFINEMENT-02  
**Phase:** 2A (infrastructure) — admin-only initial exposure

---

## Purpose

Treat the Compliance Evidence Graph as an **operational subsystem** with measurable integrity. The Graph Health service aggregates integrity validator results into dashboard-ready metrics for administrators and future platform health surfaces.

The health service **observes** graph state. It never mutates decisions, snapshots, nodes, or edges.

---

## Service location

```
backend/services/compliance_graph_health/
  __init__.py
  service.py       # report generation, scoped queries
  metrics.py       # metric definitions, severity tiers
```

**Dependency:** `compliance_evidence_graph.validation.integrity_validator` (single validation core).

---

## Health dimensions

| Dimension | Description | Source check |
|-----------|-------------|--------------|
| Decision completeness | Every decision has snapshot, nodes, required fields | `validate_decision` |
| Snapshot completeness | 1:1 decision pairing, hash present, required snapshot sections | `validate_snapshot` |
| Relationship integrity | No broken from/to refs, provenance complete | `validate_relationships` |
| Orphan nodes | Nodes without decision or source linkage | `validate_graph` |
| Orphan edges | Edges referencing missing nodes | `validate_graph` |
| Duplicate decisions | Multiple docs per `dedupe_key` | `validate_graph` |
| Duplicate snapshots | Multiple snapshots per `decision_id` | `validate_graph` |
| Supersession chain | `previous_decision_id` / `superseding_decision_id` consistency | `validate_supersession` |
| Operational links | `operational_correlation_id` resolvable where expected | `validate_operational_links` |
| Rule lineage | Lineage chain complete for governed decisions | `validate_rule_lineage` |
| Cross-tenant references | No client_id mismatch across linked entities | `validate_tenant_isolation` |
| Invalid relationship types | Edge types in allowed enum | `validate_relationships` |
| Missing provenance | Edges without required provenance block | `validate_relationships` |
| Decision quality presence | `decision_quality` block on all runtime decisions | `validate_decision` |

---

## Report schema

```json
{
  "service": "compliance_graph_health",
  "service_version": "1.0.0",
  "generated_at": "2026-06-02T12:00:00+00:00",
  "scope": {
    "client_id": null,
    "environment": "staging",
    "since": "2026-01-01T00:00:00+00:00",
    "until": null
  },
  "overall_status": "healthy",
  "summary": {
    "decisions_examined": 1240,
    "checks_passed": 14,
    "checks_failed": 0,
    "warnings": 2,
    "integrity_failure_count": 0
  },
  "metrics": {
    "decision_completeness_rate": 1.0,
    "snapshot_pairing_rate": 1.0,
    "orphan_node_count": 0,
    "orphan_edge_count": 0,
    "duplicate_dedupe_key_count": 0,
    "broken_supersession_count": 0,
    "missing_operational_link_rate": 0.02,
    "rule_lineage_complete_rate": 0.98,
    "cross_tenant_violation_count": 0,
    "decision_quality_present_rate": 1.0
  },
  "failures": [],
  "warnings": [
    {
      "check": "validate_operational_links",
      "severity": "warning",
      "count": 24,
      "sample_decision_ids": ["dec_abc"],
      "message": "Operational correlation ID present but no matching OE event"
    }
  ],
  "validator_version": "1.0.0"
}
```

### Status tiers

| `overall_status` | Condition |
|------------------|-----------|
| `healthy` | Zero integrity failures; warnings below configured threshold |
| `degraded` | Warnings exceed threshold; no structural failures |
| `unhealthy` | Any integrity failure (orphans, duplicates, cross-tenant, broken supersession) |

---

## HTTP API (admin-only, Phase 2A)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/compliance/graph/health` | Full health report (optional `client_id`, `since`) |
| GET | `/api/admin/compliance/graph/health/summary` | Summary metrics only |
| POST | `/api/admin/compliance/graph/health/validate` | Run validator on demand (sync) |

Gated by existing admin route guard. Respects tenant scope when `client_id` provided.

---

## Future integration

| Consumer | Integration |
|----------|-------------|
| Automation Control Centre | Scheduled health job; alert on `unhealthy` |
| System Health dashboard | Summary metrics widget |
| Phase 2E acceptance | Health report must show `healthy` or documented warnings only |
| Incident response | Cross-reference with OE incidents when graph integrity degrades |

---

## Performance

Health checks are **read-only** and may scan bounded windows. Default acceptance scope: last 30 days of staging shadow data.

For large tenants, support:

- `sample_rate` parameter
- `max_decisions` cap
- Async report generation (future — not required for 2A)

---

## Security

- Admin-only until tenant-scoped health is explicitly designed (Phase 7)
- Never expose raw storage documents in health responses — summaries and sample IDs only
- Cross-tenant validation runs platform-wide (admin context only)
