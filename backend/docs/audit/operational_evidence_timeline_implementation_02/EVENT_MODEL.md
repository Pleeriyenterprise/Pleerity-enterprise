# Event Model

Every `operational_evidence_events` document follows this envelope.

## Required fields

| Field | Type | Description |
|---|---|---|
| `event_id` | UUID | Immutable unique identifier |
| `occurred_at` | ISO-8601 | When the runtime event happened |
| `recorded_at` | ISO-8601 | When the index record was written |
| `category` | enum | Filter axis (scheduler, compliance, incident, …) |
| `event_type` | string | Stable machine type (JOB_RUN_STARTED, …) |
| `severity` | enum | debug \| info \| warning \| error \| critical |
| `status` | enum | started \| success \| failed \| degraded \| recovered \| … |
| `source_service` | string | Emitting service module |
| `source_component` | string | Function or component name |
| `evidence.source_collection` | string | Authoritative MongoDB collection |
| `evidence.source_id` | string | Authoritative document ID |
| `confidence.score` | int | 0–100 certainty |

## Correlation spine (sparse)

`correlation_id`, `execution_id`, `root_execution_id`, `job_run_id`, `incident_id`, `queue_item_id`, `workflow_id`, `notification_id`, `webhook_id`, `property_id`, `requirement_id`, `client_id`, `user_id`, `document_id`, `request_id`

Null when unknown — never inferred.

## Relationships object

```json
{
  "parent_event_id": "uuid|null",
  "previous_event_id": "uuid|null",
  "next_event_id": null,
  "caused_by_event_id": "uuid|null",
  "relationship_type": "triggered|caused|child_of|retry_of|recovered_from|continuation|null"
}
```

`next_event_id` always null at write time. Computed at read via `execution_sequence`.

## Execution object

```json
{
  "root_execution_id": "uuid",
  "execution_id": "uuid",
  "execution_depth": 0,
  "execution_sequence": 1
}
```

## Customer impact object

```json
{
  "classification": "no_impact|operational_only|property_affected|…",
  "scope": "none|property|portfolio|tenant|platform",
  "affected_count": 0,
  "summary": "human-readable impact statement"
}
```

## Confidence object

```json
{
  "score": 100,
  "label": "runtime_confirmed",
  "reason": "Direct instrumentation at authoritative source"
}
```

## Temporal reconstruction (Phase 10 foundation)

Optional `temporal_snapshot` — bounded JSON capturing platform belief at `occurred_at` (e.g. health score, job status). Does not modify source records.
