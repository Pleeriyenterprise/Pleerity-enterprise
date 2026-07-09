# Performance & Scalability Assessment

## Write path

- Async emit via `emit_operational_evidence`; failure logged, never blocks business logic
- Single insert + execution registry upsert per event
- Target overhead: <5ms p99 non-blocking

## Read path

| Query | Index | Target |
|---|---|---|
| Global timeline (50 events) | `(occurred_at, event_id)` | <500ms |
| Execution chain | `(root_execution_id, execution.execution_sequence)` | <2s @ 500 events |
| Incident/property filter | scoped + occurred_at | <500ms |
| Relationship walk | `caused_by_event_id`, `parent_event_id` | O(n) in chain bound |

## Scale projections

| Volume | Strategy |
|---|---|
| <1M events | Primary collection, all indexes hot |
| 1M–10M | Retention tiering; archive flag on events >90d |
| >10M | Cold archive collection; correlation_id lookup only in cold tier |

## Graph queries

Execution trees built in application layer from indexed chain query — avoids MongoDB graph engine dependency while keeping future migration path open.

## Validation (Phase 4)

Staging script will measure:

- 50-event page latency
- 200-event chain expansion
- Concurrent admin session reads
- Emit rate under scheduled job burst
