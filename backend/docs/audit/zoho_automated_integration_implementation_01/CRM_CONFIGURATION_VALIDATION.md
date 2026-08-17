# CRM_CONFIGURATION_VALIDATION

**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01`  
**Date:** 2026-07-14  

## Required configuration (staging)

| Item | Env / setting | Notes |
|---|---|---|
| Master | `ZOHO_INTEGRATION_ENABLED=true` | Keep CRM flag false until C12 |
| CRM flag | `ZOHO_CRM_SYNC_ENABLED=false` initially | Enable only after config pass |
| Kill switch | `ZOHO_KILL_SWITCH=false` | Active → expected disabled |
| OAuth client | `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` | Shared Option B |
| Refresh token | `ZOHO_CRM_REFRESH_TOKEN` | Regenerated with CREATE+UPDATE+**READ** |
| Module | `ZOHO_CRM_MODULE=Leads` | Must match READ/CREATE/UPDATE scopes |
| API | `ZOHO_API_BASE` / accounts URL | EU defaults acceptable |
| Identity field | Zoho custom `Pleerity_Lead_ID` | Unique recommended |
| Webhook secret | `ZOHO_CRM_WEBHOOK_SECRET` | Reject-only inbound |

## Scope (do not broaden to ALL)

```
ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE,ZohoCRM.modules.leads.READ
```

Operators must re-issue the CRM refresh token after adding READ.

## Observability surfaces

Status / System Health expose:

- `crm_target` / `crm_ops.configuration_complete` / `configuration_missing`
- OAuth by integration for `crm`
- Queue pending/failed, DL count, replay count
- Identity resolution order (documented on `crm_target`)

## Validation procedure (C11 — no live writes)

1. Deploy with `ZOHO_CRM_SYNC_ENABLED=false`
2. `GET /api/admin/integrations/zoho/status`
3. Confirm `crm_target.target_complete` once secrets + scopes present
4. Confirm CRM flag false; no outbound queue drain required
5. Confirm production unchanged

Record results in `CRM_LIVE_STAGING_VALIDATION.md`.
