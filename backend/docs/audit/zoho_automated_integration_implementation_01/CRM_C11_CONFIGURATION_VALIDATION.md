# CRM_C11_CONFIGURATION_VALIDATION

**Phase:** `PHASE_C_CRM_LIVE_STAGING_ACTIVATION_01` / C11  
**Date:** 2026-07-14  
**Commit:** `5613812db8d9042a8d4e107190a47212c84e25e8`  
**Staging API:** `https://pleerity-enterprise.onrender.com/api`  
**Verdict:** **C11_PASS**

---

## Preconditions observed

| Check | Result | Evidence |
|---|---|---|
| Staging converged to `5613812d` | PASS | `/api/version` → `5613812db8d9042a8d4e107190a47212c84e25e8`, `environment: staging` |
| Platform health | PASS | `/api/health` → `status: healthy`, `degraded: false` |
| `ZOHO_INTEGRATION_ENABLED` | PASS | status → `zoho_integration_enabled: true` |
| `ZOHO_CRM_SYNC_ENABLED` | PASS (dormant) | `integrations.crm: false` |
| CRM refresh token present | PASS | `oauth_by_integration.crm.refresh_token_configured: true`, `source: per_integration` |
| Expected scopes include READ | PASS | `CREATE,UPDATE,READ` on registry / `crm_target.expected_scope` |
| No legacy `ZOHO_REFRESH_TOKEN` fallback | PASS | `legacy_refresh_token_configured: false`; CRM `using_legacy_fallback: false` |
| CRM module / identity config | PASS | `crm_target.module: Leads`, `identity_field: Pleerity_Lead_ID`, `target_complete: true`, `missing: []` |
| Field mapping / resolution order | PASS | documented on `crm_target` + code registry; forbidden matchers email/name/heuristic |
| CRM inactive while flag false | PASS | `crm_ops.enabled: false`, `incident_policy: disabled_expected` |
| No outbound CRM on manual sync attempt | PASS | `POST .../zoho/sync` upsert → `skipped` / `integration_disabled`, empty `sync_id` |
| CRM sync history empty | PASS | `GET .../sync-runs?integration=crm` → `runs: []` |
| Queue clear | PASS | pending/processing `0` |
| Dead letter clear | PASS | unresolved `0`; `crm_ops.dead_letter_count: 0` |
| Production unchanged | PASS | prod `/api/version` still `89217062…`; prod Zoho status **404** (not exposed) |

---

## crm_ops (dormant)

- `enabled: false`
- `configuration_complete: true`
- `oauth_status: awaiting_refresh` (expected until first live CRM API call)
- `incident_policy.level: disabled_expected` / `crm_sync_disabled`
- `next_expected_sync: manual_only_no_cron`

## Notes / conditions

1. Zoho layer `operational_health.overall_status` may show **degraded** while access tokens are uncached (`oauth_token_valid: false`). Platform `/health` remains **healthy**. CRM policy correctly reports **disabled_expected**, not an actionable incident.
2. `POST /internal/.../webhooks/crm` returned `401 webhook_secret_not_configured` — inbound still does not mutate Pleerity. Recommend configuring `ZOHO_CRM_WEBHOOK_SECRET` before relying on signed reject paths.
3. Live custom-field existence in Zoho sandbox (`Pleerity_Lead_ID` etc.) is not remotely introspectable without CRM READ calls; operators confirmed sandbox custom fields as C12 precondition. Config surface asserts identity field contract.

## Gate to C12

C11 **PASS**. Proceed to C12 only after:

1. Set staging `ZOHO_CRM_SYNC_ENABLED=true` and redeploy / restart  
2. Confirm status `integrations.crm: true`  
3. Execute exactly one manual `upsert_lead` on a dedicated staging test lead  

**Blocking in this environment:** no `RENDER_API_KEY` available to flip the staging env var from the agent. Operator/dashboard action required.
