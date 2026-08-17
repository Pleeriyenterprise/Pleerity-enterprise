# Zoho Integration Architecture

**Programme:** ZOHO AUTOMATED INTEGRATION IMPLEMENTATION  
**Date:** 2026-07-09

## Pattern

```
Pleerity Platform (SoR)
        ↓
ZohoIntegrationService (services/integrations/zoho/service.py)
        ↓
Per-app adapters (adapters/*.py)
        ↓
ZohoHttpClient + OAuth
        ↓
Zoho API
```

**Inbound:**

```
Zoho Webhook → verifier → handlers → governed action only → audit_logs
```

## Components

| Component | Path | Role |
|-----------|------|------|
| Config / flags | `config.py` | Feature flags, kill switch, env isolation |
| OAuth | `oauth.py` | Token refresh, DB cache |
| HTTP client | `client.py` | API calls, rate-limit awareness, circuit breaker |
| Sync store | `sync_store.py` | Runs, queue, dead-letter, external keys |
| Registry | `registry.py` | Field mappings, authority blocks |
| Service | `service.py` | Single entry for all sync |
| Adapters | `adapters/` | analytics, crm, campaigns, sign, books, workdrive |
| Webhooks | `webhooks/` | Verification + handlers |
| Admin API | `routes/integrations/zoho/admin.py` | Status, replay, manual sync |
| Webhook API | `routes/integrations/zoho/webhooks.py` | Sign, campaigns, CRM reject, books reject |

## Collections

- `zoho_sync_runs` — every sync attempt
- `zoho_sync_dead_letter` — failed syncs for replay
- `zoho_sync_queue` — async CRM event queue
- `zoho_oauth_tokens` — access token cache per environment
- `zoho_external_keys` — Pleerity ID → Zoho ID mapping

## Jobs

- `zoho_sync_queue` — process queue
- `zoho_analytics_export` — scheduled read-only export
- `zoho_books_export` — finance summary export
- `zoho_campaigns_export` — audience + suppression (if enabled)

## Default state

**All integrations disabled.** `ZOHO_INTEGRATION_ENABLED=false` hides admin and webhook routes (404).
