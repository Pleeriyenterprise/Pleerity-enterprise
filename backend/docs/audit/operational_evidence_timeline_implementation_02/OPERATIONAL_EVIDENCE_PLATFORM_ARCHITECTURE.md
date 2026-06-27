# Operational Evidence Platform — Architecture (IMPLEMENTATION-02)

**Programme:** OPERATIONAL-EVIDENCE-TIMELINE-IMPLEMENTATION-02  
**Status:** Phase 0 + Phase 1 foundation implemented  
**Date:** 2026-06-02

---

## Executive summary

The Operational Evidence Timeline proposal is strengthened into an **Operational Evidence Platform**: an append-only, indexed correlation layer over existing authoritative operational stores. The Timeline is one presentation layer; the platform supports execution trees, operational stories, future analytics, and AI explainability without introducing duplicate operational authority.

---

## Architectural enhancements over IMPLEMENTATION-01

| Enhancement | Rationale |
|---|---|
| **Explicit relationship model** | Timestamps alone cannot reconstruct causality; parent/c caused_by/previous edges form execution trees |
| **Operational Story abstraction** | Default investigation UX — curated narrative steps over raw event streams |
| **Expanded customer impact taxonomy** | 14 classifications searchable/reportable beyond simple scope |
| **Confidence metadata** | Communicates certainty without replacing authority (100 = runtime confirmed) |
| **Business event catalogue** | Domain events (compliance valid/invalid, evidence approved) correlate with infrastructure |
| **Temporal snapshots** | Optional `temporal_snapshot` on events for time-reconstruction (Phase 10 foundation) |
| **Execution registry** | `operational_evidence_executions` — non-authoritative index for fast story roots |
| **Presentation-agnostic API** | Views: timeline, chain, tree, story, tenant/property/incident/job — same underlying events |
| **AI-ready structure** | Structured relationships + evidence pointers; narratives generated at read time |
| **Intelligence foundation** | Aggregation shortcuts for retry loops, failure families, customer impact — no ML yet |

---

## Authority model (unchanged)

Authoritative sources remain sole operational truth:

- `job_runs`, `incidents`, queues, `score_ledger_events`, `message_logs`, `audit_logs`
- `scheduler_heartbeat`, health summary, Control Centre, System Health, Platform Status

The platform **indexes and correlates** via `operational_evidence_events` with mandatory `evidence.source_collection` + `source_id` pointers.

---

## Collections

| Collection | Role |
|---|---|
| `operational_evidence_events` | Append-only evidence index with relationships |
| `operational_evidence_executions` | Execution summary registry (event_count, last_event — not authoritative) |
| `operational_evidence_annotations` | Editable admin notes (audited separately from runtime evidence) |

---

## Event envelope (refined)

See `EVENT_MODEL.md` for full schema. Key additions:

- `relationships`: parent_event_id, previous_event_id, caused_by_event_id, relationship_type
- `execution`: root_execution_id, execution_id, execution_depth, execution_sequence
- `customer_impact`: classification + scope + affected_count + summary
- `confidence`: score + label + reason
- `temporal_snapshot`: optional bounded state at event time
- `evidence`: source_collection, source_id, deep_link, payload_hash

**Immutability:** `next_event_id` and `child_count` are computed at query time — never mutated post-insert.

---

## Correlation spine

`OperationalContext` (contextvars) propagates IDs through:

- HTTP middleware → API handlers
- `job_runner.run_instrumented` → job evidence
- `compliance_recalc_queue.enqueue` → queue evidence
- `incident_lifecycle_service.record_operational_detection` → incident evidence

Unknown relationships remain **null** — never fabricated.

---

## API surface

Prefix: `/api/admin/observability/evidence`

| Endpoint | View |
|---|---|
| `GET /events` | Paginated global timeline |
| `GET /chains` | Execution chain + tree |
| `GET /stories` | Operational Story (default investigation) |
| `GET /views/incident/{id}` | Incident timeline + story |
| `GET /views/job-run/{id}` | Job timeline + story |
| `GET /views/tenant|property|requirement/{id}` | Scoped timelines |
| `GET /intelligence/shortcuts` | Intelligence foundation |
| `POST /annotations` | Admin annotations |

---

## Producers (Phase 1 wired)

| Boundary | Events |
|---|---|
| `job_runner.run_instrumented` | JOB_RUN_STARTED, COMPLETED, FAILED, DEGRADED |
| `incident_lifecycle_service` | INCIDENT_OPENED, DEGRADED, REPEAT |
| `compliance_recalc_queue.enqueue` | QUEUE_ITEM_CREATED |

Phase 2+: notifications, score ledger, business domain events, deployments.

---

## Frontend

`/admin/ops/evidence-timeline` — Operational Story (default), Raw Timeline, Execution Tree views with filters, correlation copy, deep links.

---

## Performance & scale

- Cursor pagination on `(occurred_at, event_id)`
- Indexed relationship traversal (parent_event_id, caused_by_event_id, root_execution_id)
- Target: <500ms for 50-event page; chain queries bounded at 1000 events
- Retention tiers documented for Phase 4 (hot/warm/cold archive)

---

## Governance

- Runtime evidence: append-only, immutable
- Annotations: separate collection, editable, audited
- No silent modification of historical evidence

---

## Related documents

- `EVENT_MODEL.md` — full event schema
- `RELATIONSHIP_MODEL.md` — causality graph
- `CORRELATION_STRATEGY.md` — spine propagation
- `OPERATIONAL_STORY_MODEL.md` — story computation
- `CUSTOMER_IMPACT_MODEL.md` — impact taxonomy
- `CONFIDENCE_MODEL.md` — certainty levels
- `BUSINESS_EVENT_CATALOGUE.md` — domain events
- `FINAL_ARCHITECTURE_REVIEW.md` — comparison to IMPLEMENTATION-01
