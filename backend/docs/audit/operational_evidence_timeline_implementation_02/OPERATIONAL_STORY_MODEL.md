# Operational Story Model

An **Operational Story** is a computed view — not a separate authority.

## Purpose

Administrators see a curated narrative:

```
Compliance Recalculation
  Started → Queue created → Worker claimed → Score changed → Completed
  Customer impact: No impact
```

Raw evidence remains accessible via Timeline and Execution Tree views.

## Generation

`build_operational_story(items)` where `items` = ordered execution chain:

1. Derive title from dominant event types (compliance, job, incident, notification)
2. Map event_type → human label ("JOB_RUN_STARTED" → "Started")
3. Aggregate customer impact (worst classification wins)
4. Determine overall status from terminal event

## API

`GET /api/admin/observability/evidence/stories?root_execution_id=…`

Returns:

- `title`, `status`, `steps[]`, `customer_impact`, `tree`, `items`, `raw_evidence_available: true`

## Default UI mode

Frontend defaults to **Operational Story** view; user toggles to Raw Timeline or Execution Tree.

## Future

Stories may be cached in read replicas for heavy investigations — cache invalidation keyed by `root_execution_id` event_count from execution registry.
