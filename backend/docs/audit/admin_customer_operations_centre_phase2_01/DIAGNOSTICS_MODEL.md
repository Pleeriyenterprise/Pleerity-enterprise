# Diagnostics Model

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Runtime diagnostics (support-safe)

| Field | Purpose |
|-------|---------|
| runtime_version | Current contract version |
| resolved_at | Last resolution timestamp |
| runtime_source | Resolver identity (not stack traces) |
| runtime_cache | warm/cold, TTL — explains read-path caching |
| mirror_freshness | billing_last_synced_at age, stale threshold |
| legacy_drift | compare_runtime_with_legacy flags |
| capability_evaluation | entry count, via contract |

## Background processing

Sampled job groups via `evaluate_background_runtime`:

- daily_reminders, monthly_digest, renewal_reminders, compliance_monitoring, queue_processing

Per job: decision (CONTINUE/PAUSE/SKIP/TERMINATE), reason, policy key.

Platform scheduler health **not** duplicated — link to System Health.

## Webhook diagnostics

Enhanced per-event: processing_duration_ms, retry_count, replay_eligible (always false with explanation).

## API fields

- `snapshot.runtime_diagnostics`
- `snapshot.background_processing`
- `snapshot.webhook_diagnostics`

No developer-only internals (raw payloads, env secrets).
