# CRM_C12_LIVE_STAGING_VALIDATION

**Phase:** `PHASE_C_CRM_LIVE_STAGING_ACTIVATION_01` / C12  
**Date:** 2026-07-14  
**Deploy baseline:** `5613812d`  
**Status:** **BLOCKED — CRM flag still false**

Companion JSON: `CRM_C12_LIVE_STAGING_VALIDATION.json`

---

## Gate state after C11

C11 **PASS** (see `CRM_C11_CONFIGURATION_VALIDATION.md`).

C12 cannot execute live Zoho writes while `integrations.crm === false`.

| Required action | Owner | Status |
|---|---|---|
| Set staging `ZOHO_CRM_SYNC_ENABLED=true` | Render ops / dashboard | **PENDING** |
| Redeploy/restart staging | Render | **PENDING** |
| Confirm `/admin/integrations/zoho/status` shows `crm: true` | Validator | **PENDING** |
| Run `tmp_crm_c12_live_staging_activation.py` once | Agent/operator | Ready (script committed after mapping patch) |

**Agent limitation:** no `RENDER_API_KEY` in this environment — cannot flip the env var autonomously.

---

## Planned C12 sequence (when flag is on)

1. Create dedicated staging test lead (`POST /admin/leads`) — not customer data  
2. Exactly one `POST /admin/integrations/zoho/sync` `upsert_lead` — **no auto-retry**  
3. Assert identity: no prior external key → `Pleerity_Lead_ID` lookup → create → persist key  
4. Assert success response includes `external_id` + `metadata.result_summary.identity_source`  
5. Update Pleerity lead → second upsert → external key reuse / PUT  
6. `mark-lost` → status-only CRM update (no delete/archive)  
7. Inbound webhook still non-mutating; DL empty; other Zoho flags off; prod pin unchanged  

## Mapping note (pre-C12 hotfix)

Staging leads often store `name` without `last_name`. Mapping now derives Zoho `Last_Name` from Pleerity `name` when needed (display mapping only — not identity). Patch must land on staging before/alongside C12 execution.

## Current verdict contribution

C12 incomplete → overall activation cannot be `CRM_STAGING_PASS`.
