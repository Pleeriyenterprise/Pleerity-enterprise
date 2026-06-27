# Relationship Model

The platform models **causality** as a directed graph, not a flat chronological list.

## Edge types

| relationship_type | Semantics |
|---|---|
| `triggered` | Root cause initiated a chain (scheduler → job) |
| `caused` | Direct causal predecessor (job → queue item) |
| `child_of` | Hierarchical nesting (worker step under job) |
| `continuation` | Sequential step in same execution (previous → next via sequence) |
| `retry_of` | Retry attempt linked to failed attempt |
| `recovered_from` | Recovery action linked to incident/failure |
| `correlated` | Weak association when causality unknown but IDs match |

## Stored vs computed

| Field | Storage | Notes |
|---|---|---|
| `parent_event_id` | Stored on child | Tree hierarchy |
| `caused_by_event_id` | Stored on child | Explicit causality |
| `previous_event_id` | Stored on child | Backward chain link |
| `next_event_id` | **Computed** | Immutable — derived from execution_sequence |
| `child_count` | **Computed** | Count of events referencing this as parent/cause |

## Execution tree reconstruction

1. Query by `root_execution_id` sorted by `execution.execution_sequence`
2. Build nodes with computed `child_count`
3. Build edges from `parent_event_id`, `caused_by_event_id`, `previous_event_id`
4. Root = first event with no parent and no caused_by

API: `GET /api/admin/observability/evidence/chains?root_execution_id=…`

## AI readiness

Structured edges enable future queries:

- "What caused this incident?" → walk `caused_by_event_id` backward
- "What did this job trigger?" → walk forward via parent/cause references
- No narrative text stored — graph is machine-readable
