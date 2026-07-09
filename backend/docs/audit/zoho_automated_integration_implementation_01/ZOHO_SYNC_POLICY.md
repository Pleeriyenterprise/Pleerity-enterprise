# Zoho Sync Policy

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Rules

1. All syncs go through `ZohoIntegrationService.run_sync()` — no direct DB writes from adapters.
2. Every attempt recorded in `zoho_sync_runs`.
3. Failures after retries → `zoho_sync_dead_letter`.
4. CRM events enqueued via `zoho_sync_queue`; processed by `zoho_sync_queue` job.
5. **One-way CRM** — outbound only; inbound webhooks rejected.
6. **Read-only Analytics** — aggregates only; PII check before export.
7. **Campaigns** requires `ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED=true`.
8. Kill switch `ZOHO_KILL_SWITCH=true` stops all integrations immediately.

## Retry

- Max 3 attempts per sync run (tracked on run document)
- Circuit breaker opens after 5 API failures per integration (5 min)
- Manual replay via `POST /api/admin/integrations/zoho/replay`

## Scheduling

| Job | Frequency | Integration |
|-----|-----------|-------------|
| zoho_sync_queue | On schedule / manual | CRM queue |
| zoho_analytics_export | Daily (when scheduled) | Analytics |
| zoho_books_export | Monthly (when scheduled) | Books |
| zoho_campaigns_export | Weekly (when scheduled) | Campaigns |

Scheduler registration in `server.py` is **deferred** until staging pilot — jobs available via admin job runner.

## Idempotency

- CRM upsert by `zoho_external_keys` mapping
- Queue items marked completed after successful sync
