# Stage Y — Twin Webhook Ingestion Connector

**Authority:** `STAGE-Y-TWIN-WEBHOOK-INGESTION-CONNECTOR-AUTHORITY-01`  
**Phase:** Capture-first (default) — ingest deferred until real Twin run events are inspected.

## Architecture

```
Twin POST /webhooks (run.completed)
        ↓
POST /api/internal/discovery/twin/webhooks  (HMAC verify)
        ↓
GET  /v1/agents/{agent_id}/runs/{run_id}/events
        ↓
discovery_twin_run_event_captures (MongoDB)
        ↓
[when enabled] TwinProvider.ingest_async() → discovery_prospects
```

## Enable (staging only)

```bash
DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true
DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=true          # default — capture only
TWIN_API_KEY=...
TWIN_WEBHOOK_SIGNING_SECRET=...
TWIN_DISCOVERY_AGENT_ID=agent_...
TWIN_DISCOVERY_CAMPAIGN_ID=DCAMP-...              # required only for auto-ingest
DISCOVERY_TWIN_WEBHOOK_TOKEN=...                # optional Bearer on CVP endpoints
```

## Register Twin webhook

```bash
curl -X POST "https://build.twin.so/v1/agents/${TWIN_DISCOVERY_AGENT_ID}/webhooks" \
  -H "x-api-key: ${TWIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<staging-cvp>/api/internal/discovery/twin/webhooks",
    "events": ["run.completed", "run.failed"]
  }'
```

Store `signing_secret` from the response in `TWIN_WEBHOOK_SIGNING_SECRET`.

## Inspect captured events

After a Twin run completes:

```bash
# Health
curl https://<staging>/api/internal/discovery/twin/health

# Manual pull (no webhook)
curl -X POST https://<staging>/api/internal/discovery/twin/reconcile \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_...","run_id":"run_..."}'

# Inspect capture
curl https://<staging>/api/internal/discovery/twin/captures/DTCE-...
```

MongoDB collections:

- `discovery_twin_webhook_receipts` — idempotency + status
- `discovery_twin_run_event_captures` — full event stream + diagnostics

Review `event_diagnostics.top_level_event_keys` and `records_candidates` before enabling extraction.

## Enable ingest (later)

Only after export location is proven on real Twin events:

```bash
DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=false
DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED=true
DISCOVERY_PROVIDER_TWIN_ENABLED=true
DISCOVERY_MODULE_ENABLED=true
DISCOVERY_PROVIDER_LAYER_ENABLED=true
```

## Tests

```bash
cd backend
python -m pytest tests/test_twin_webhook_connector.py -q
```

## Hard prohibitions

No `LeadService`, `DiscoveryImportService`, approval APIs, CRM writes, auto-import, outreach, or production flags by default.
