# CRM Searchability Recovery Report

**Generated:** `2026-07-14T19:46:16+00:00` (recovery) / C12 dedicated re-run `19:54:14+00:00`  
**Staging SHA:** `476b6c970c1a7deecfbcd3963cf3fe5da50f0b5b`  
**Production SHA:** `89217062481b4eb858a8b530ec90c83de067a4be` (unchanged)  
**Recovery verdict:** **PASS**  
**C12 verdict:** **CRM_STAGING_PASS_WITH_CONDITIONS**  
**Combined:** **CRM_STAGING_PASS_WITH_CONDITIONS**

---

## Prefight

| Check | Result |
|---|---|
| Staging redeployed / healthy | PASS — `476b6c97…`, `/health` healthy |
| Production pin | PASS — `89217062…` |
| `ZOHO_CRM_SYNC_ENABLED` | PASS — `crm=true` |
| CRM OAuth per-integration | PASS — `refresh_token_source=per_integration` |
| Legacy token fallback | PASS — `legacy_refresh_token_configured=false`, `using_legacy_fallback=false` |
| Expected scopes | CREATE / UPDATE / READ on leads |

Pre-recovery backlog: queue pending **1**, unresolved DL **1** (`ZDL-8601BEA054E2`).

---

## Read-only Search probe

After OAuth refresh (per-integration token; `refresh_token_source_cached=per_integration`):

| Probe | Result |
|---|---|
| `GET /crm/v6/settings/fields?module=Leads` | 200 |
| Field | `display_label=Pleerity Lead ID`, `api_name=Pleerity_Lead_ID`, `data_type=text`, `id=625014000001931007`, `searchable=true`, unique `{case_sensitive:false}` |
| `GET /crm/v6/Leads/search?criteria=(Pleerity_Lead_ID:equals:PLEERITY_SEARCHABILITY_PROBE_NO_MATCH)` | **204** |
| `INVALID_QUERY` | **Absent** |

Lookup strategy unchanged: local external key → Search API on `Pleerity_Lead_ID` → create → persist.

---

## Governed recovery (prior fail artefacts)

| Step | Result |
|---|---|
| Recovery lead | `LEAD-20260714090602-6D5752` |
| Controlled upsert (searchable path) | `ZSYNC-BAAC8BDFB65D` → `crm_outbound_create_ok` → CRM id `625014000001936001` |
| DL replay once `ZDL-8601BEA054E2` | `ZSYNC-DDF009711FF6` → `crm_outbound_update_ok` (same CRM id) |
| Process queue once | `processed=1`, `failed=0` |
| Unexpected create/duplicate | **None** — single CRM id for recovery lead |
| Mongo direct clears | **Not used** |

Post-recovery: queue **0**, DL **0**, `crm_ops.healthy=true`, `oauth_status=healthy`.

---

## C12 dedicated lead (supersedes invalid reuse)

An earlier C12 attempt reused the recovery lead (same phone colliding on admin create). That attempt is **invalidated**.

Dedicated re-run:

| | |
|---|---|
| Lead | `LEAD-20260714195426-198E68` |
| CRM id | `625014000001948001` (≠ recovery id) |
| Create evidence | Queue drain `lead.created` `ZSYNC-2327F1C59A60` → `crm_outbound_create_ok` |
| Later ops | All `crm_outbound_update_ok` / PUT via `external_key` |
| mark_lost | Status update only (PUT), same CRM id |
| Idempotency | Two further upserts → same single CRM id |
| Queue / DL after | **0 / 0** |
| Inbound CRM webhook | Rejected (`401`) |
| Other Zoho products | campaigns/books/sign/workdrive **off**; analytics flag remains on but **not executed** by this run |
| Production | Unchanged |

---

## Conditions (why not unconditional PASS)

1. `analytics_flag_still_enabled_not_executed` — Analytics remains enabled from prior Phase B; this run did not export.  
2. `first_crm_create_occurred_via_queue_drain_before_explicit_sync` — With CRM enabled, admin lead create enqueues `lead.created`; drain performed the create before the explicit admin upsert (which correctly updated).

Neither condition weakens identity governance or searchability.

---

## Final verdict

**CRM_STAGING_PASS_WITH_CONDITIONS**
