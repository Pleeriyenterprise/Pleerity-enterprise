# Zoho Sync Observability

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION

## Admin endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/admin/integrations/zoho/status` | Flag snapshot, credentials configured |
| `GET /api/admin/integrations/zoho/sync-runs` | Recent sync history |
| `POST /api/admin/integrations/zoho/replay` | Dead-letter replay |
| `POST /api/admin/integrations/zoho/sync` | Manual governed sync |
| `POST /api/admin/integrations/zoho/process-queue` | Drain CRM queue |

## MongoDB queries

```javascript
// Failed syncs last 24h
db.zoho_sync_runs.find({ status: { $in: ["failed", "dead_letter"] } }).sort({ created_at: -1 })

// Pending queue depth
db.zoho_sync_queue.countDocuments({ status: "pending" })

// Unresolved dead letters
db.zoho_sync_dead_letter.countDocuments({ resolved: false })
```

## Audit logs

Filter `audit_logs` where `metadata.action_type` in (`ZOHO_SYNC`, `ZOHO_WEBHOOK`).

## Metrics to monitor

| Metric | Alert threshold |
|--------|-----------------|
| Sync failure rate | > 10% in 1h |
| Dead-letter depth | > 50 unresolved |
| Queue lag | > 100 pending > 1h |
| Circuit breaker open | Any integration |
| OAuth refresh failures | Any in 15m |

## Job runs

Standard `job_runs` collection tracks `zoho_*` jobs via admin job execution panel.
