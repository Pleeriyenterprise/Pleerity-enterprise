# Correlation Strategy

## ID definitions

| ID | Scope | Origin |
|---|---|---|
| `correlation_id` | Cross-subsystem trace | HTTP `X-Correlation-Id`, queue correlation, or explicit |
| `execution_id` | Single logical operation | UUID at chain root |
| `root_execution_id` | Top of execution tree | Same as execution_id at root; inherited by children |
| Domain IDs | Entity scope | Copied from authoritative records at emit time |

## Propagation matrix

| Source | Inherits | Sets |
|---|---|---|
| HTTP middleware | — | correlation_id, request_id |
| `run_instrumented` | context | execution_id, job_run_id |
| Queue enqueue | context + queue doc | correlation_id, property_id, client_id |
| Queue worker | queue item metadata | all queue fields |
| Incident detection | job context | incident_id |
| Notification send | context | notification_id |

## Rules

1. **Inherit automatically** via `OperationalContext` (contextvars)
2. **Never fabricate** — if correlation unknown, emit with null
3. **Fork depth** on queue claim / worker start via `ctx.fork_execution()`
4. **Sequence** monotonic per root via `ctx.next_sequence()` at each emit

## Index support

- `(correlation_id, occurred_at)`
- `(root_execution_id, execution.execution_sequence)`
- `(job_run_id, occurred_at)`, `(incident_id, occurred_at)`, etc.

Added to `job_runs` and `score_ledger_events`: `(correlation_id, created_at)` for federation queries.
