# Compliance Evidence Graph — Data Model & Relationship Strategy

**Programme:** COMPLIANCE-EVIDENCE-GRAPH-AND-EXPLAINABLE-COMPLIANCE-INTELLIGENCE-01  
**Refinement:** COMPLIANCE-EVIDENCE-GRAPH-ARCHITECTURE-REFINEMENT-01

---

## Primary entities

| Entity | Collection | Document |
|--------|------------|----------|
| Compliance Decision | `compliance_decisions` | `COMPLIANCE_DECISION_MODEL.md` |
| Decision Snapshot | `compliance_decision_snapshots` | `COMPLIANCE_DECISION_MODEL.md` |
| Graph node | `compliance_evidence_nodes` | below |
| Graph edge | `compliance_evidence_edges` | below (with provenance) |

## Node document schema (`compliance_evidence_nodes`)

```json
{
  "node_id": "ceg_<uuid>",
  "node_type": "compliance_decision",
  "decision_id": "dec_<uuid>",
  "snapshot_id": "snap_<uuid>",
  "dedupe_key": "authority_sync:req_abc:2026-06-28T10:00:00Z:semantic_state_valid",
  "occurred_at": "2026-06-28T10:00:00.123456+00:00",
  "recorded_at": "2026-06-28T10:00:00.234567+00:00",
  "client_id": "uuid",
  "property_id": "uuid",
  "requirement_id": "uuid",
  "correlation_id": "corr_uuid",
  "environment": "staging",
  "build_sha": "49eb7978…",
  "source": {
    "collection": "requirements",
    "id": "req_abc",
    "version": null
  },
  "summary": "Requirement authority sync: semantic_state → VALID",
  "status": "success",
  "severity": "info",
  "evidence_quality": {
    "authority": "requirement_evidence_authority",
    "confidence": 100,
    "confidence_label": "runtime_confirmed",
    "verification_status": "verified",
    "verification_method": "authority_sync",
    "collection_date": "2026-06-28T09:55:00+00:00",
    "expiry": "2027-06-28",
    "superseded": false,
    "conflicts": [],
    "missing_dependencies": []
  },
  "decision": null,
  "metadata": {
    "backfill": false
  },
  "supersedes_node_id": null,
  "operational_event_id": null,
  "retention": { "tier": "hot" }
}
```

**Note:** `decision` inline blob removed for `compliance_decision` nodes — decision authority lives in `compliance_decisions`. Traversal nodes carry `decision_id` + `snapshot_id` pointers only.

### Required fields (all nodes)

| Field | Rule |
|-------|------|
| `node_id` | Unique, server-generated |
| `node_type` | Enum from taxonomy |
| `dedupe_key` | Unique per logical fact; idempotent emit |
| `occurred_at` | When the fact happened in business time |
| `recorded_at` | When indexed |
| `source.collection` + `source.id` | Authoritative pointer (mandatory) |
| `summary` | Human-readable, non-speculative |

### Scoped identifiers (when known)

Populate `client_id`, `property_id`, `requirement_id`, `document_id`, `correlation_id` for query axes. Null if genuinely unknown — never guess.

---

### Required fields (all nodes)

| Field | Rule |
|-------|------|
| `node_id` | Unique, server-generated |
| `node_type` | Enum from taxonomy |
| `dedupe_key` | Unique per logical fact; idempotent emit |
| `occurred_at` | When the fact happened in business time |
| `recorded_at` | When indexed |
| `source.collection` + `source.id` | Authoritative pointer (mandatory) |
| `summary` | Human-readable, non-speculative |
| `decision_id` | Required on all nodes downstream of a compliance decision |

---

## Edge document schema (`compliance_evidence_edges`) — with provenance

```json
{
  "edge_id": "ceg_edge_<uuid>",
  "from_node_id": "ceg_…",
  "to_node_id": "ceg_…",
  "edge_type": "based_on_evidence",
  "relationship_strength": "authoritative",
  "occurred_at": "2026-06-28T10:00:00+00:00",
  "recorded_at": "2026-06-28T10:00:00.234567+00:00",
  "dedupe_key": "based_on_evidence:ceg_a:ceg_b",
  "provenance": {
    "why_exists": "Decision dec_abc assessed VALID using verified Gas Safety certificate",
    "created_by_component": "compliance_evidence_graph.emit_service",
    "created_by_authority": "requirement_evidence_authority.sync_requirement_evidence_authority",
    "created_at": "2026-06-28T10:00:00.234567+00:00",
    "decision_id": "dec_abc",
    "runtime_event_id": null,
    "operational_event_id": "ev_…",
    "correlation_id": "corr_uuid",
    "is_active": true,
    "superseded_by_edge_id": null
  },
  "metadata": {
    "rule": "verified_document_wins_over_extraction"
  }
}
```

### Provenance fields (required on every edge)

| Field | Rule |
|-------|------|
| `why_exists` | Human-readable justification — non-speculative |
| `created_by_component` | Code component that created the edge |
| `created_by_authority` | Authoritative service that triggered creation |
| `created_at` | Edge creation timestamp |
| `decision_id` | Decision that references this relationship (when applicable) |
| `runtime_event_id` | Originating runtime event ID (when applicable) |
| `operational_event_id` | Linked OE event (when applicable) |
| `is_active` | `false` when superseded; edge never deleted |
| `superseded_by_edge_id` | Replacement edge when relationship superseded |

### Edge rules

- Edges are **immutable** append-only — supersession sets `is_active: false` + new edge.
- `relationship_strength`: `authoritative` | `inferred` | `correlated` (inferred only from explicit engine output, never LLM).
- Cycles forbidden except `correlates_with` (canonical ordering).
- Relationships are **auditable** to the same standard as nodes.

---

## Graph Service response envelope (replaces raw Explain This for consumers)

All external consumers receive responses from `compliance_graph_service` — see `GRAPH_SERVICE_LAYER.md`.

`explain_decision()` payload includes:

```json
{
  "executive_summary": "…",
  "decision": { "decision_id": "…", "decision_type": "…", "decision_outcome": "…" },
  "decision_reasoning": [
    {
      "step": 1,
      "statement": "Gas Safety certificate verified on 2026-06-28",
      "authoritative_references": { "node_ids": ["ceg_doc_1"], "snapshot_fields": ["human_approvals"] },
      "confidence": 100
    }
  ],
  "snapshot_summary": { "snapshot_id": "…", "snapshot_timestamp": "…" },
  "evidence_used": [ ],
  "applicable_legislation": [ ],
  "applicable_local_rules": [ ],
  "timeline": [ ],
  "operational_history": [ ],
  "confidence_assessment": { "overall": 95, "label": "multi_source_agreement" },
  "outstanding_uncertainty": [ ],
  "insufficient_evidence": false,
  "recommended_actions": [ ]
}
```

When `insufficient_evidence: true`, `executive_summary` must state: **"Insufficient evidence available."**

---

## Compliance Replay output

`replay_decision()` returns **ordered node list** + **derived phases** from snapshot + graph (not LLM):

| Phase | Source |
|-------|--------|
| `requirements_determined` | snapshot `rules_version` + `applicable_jurisdiction` |
| `evidence_collected` | snapshot `evidence_version` |
| `extraction_applied` | snapshot `ai_extraction_results` |
| `human_review` | snapshot `human_approvals` |
| `authority_sync` | snapshot `decision_reasoning_inputs` |
| `score_recalculated` | snapshot `compliance_score` |
| `risk_updated` | snapshot `risk_score` |
| `reminder_adjusted` | decision-linked reminder nodes |
| `decision_recorded` | `compliance_decisions` record |

Replay is **deterministic**: same `decision_id` → same replay JSON. Historical replay uses snapshot only.

---

## Decision comparison output

See `COMPLIANCE_DECISION_MODEL.md` — `compare_decision()` / `compare_decision_snapshots()` structured diff.

---

## Index strategy (`database.py`)

### `compliance_decisions`

See `COMPLIANCE_DECISION_MODEL.md`.

### `compliance_decision_snapshots`

See `COMPLIANCE_DECISION_MODEL.md`.

### `compliance_evidence_nodes`

- `(client_id, occurred_at DESC, node_id DESC)` — tenant timeline
- `(property_id, occurred_at DESC)` — property scope
- `(requirement_id, occurred_at DESC)` — requirement scope
- `(node_type, occurred_at DESC)` — type filter
- `(correlation_id, occurred_at ASC)` — correlation spine
- `node_id` unique
- `dedupe_key` unique
- `(source.collection, source.id, node_type)` — source dedup / backfill
- `(decision_id, occurred_at DESC)` — decision-scoped traversal

### `compliance_evidence_edges`

- `(from_node_id, edge_type)`
- `(to_node_id, edge_type)`
- `(provenance.decision_id, recorded_at DESC)`
- `(provenance.correlation_id, recorded_at ASC)`
- `(provenance.is_active, edge_type)` — active relationship queries
- `edge_id` unique
- `dedupe_key` unique

---

## Idempotency & backfill

| Mode | `dedupe_key` | `evidence_quality.confidence` | `metadata.backfill` |
|------|--------------|------------------------------|---------------------|
| Runtime emit | `{node_type}:{source.collection}:{source.id}:{fact_signature}` | 100 | false |
| Backfill | same pattern | 40–80 (indirect) | true |

Backfill reads authoritative sources only — never mutates them.

---

## Bridge to Operational Evidence

OE event metadata extension (non-breaking):

```json
{
  "metadata": {
    "compliance_graph_node_id": "ceg_…"
  }
}
```

CEG node optional field:

```json
{
  "operational_event_id": "ev_…"
}
```

Join recipe: `correlation_id` + explicit `correlates_with` edges.
