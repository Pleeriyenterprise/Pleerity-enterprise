# Phase B — Analytics Validation Plan

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION  
**Date:** 2026-07-10  
**Prerequisite:** `PHASE_B_ANALYTICS_READINESS_CHECKLIST.md` complete  
**Constraint:** This document is a plan only. **Do not** enable `ZOHO_ANALYTICS_SYNC_ENABLED` or run export until governance authorises execution.

---

## 1. Objective

Prove a single **manual**, **aggregate-only** Analytics export from Pleerity staging to Zoho Analytics sandbox succeeds, is observable, and can be killed/rolled back — without enabling other integrations or wiring cron.

---

## 2. Pre-flight (before flag enable)

| # | Check | Pass criterion |
|---|-------|----------------|
| P1 | Staging SHA known | `/api/version` recorded |
| P2 | Phase A still healthy | Master on; other integrations false |
| P3 | Secrets present | `ZOHO_ANALYTICS_REFRESH_TOKEN`, `ZOHO_ANALYTICS_WORKSPACE_ID`, `ZOHO_ANALYTICS_VIEW_ID`, `ZOHO_ANALYTICS_ORG_ID` |
| P4 | Admin status (flag still false) | `oauth_by_integration.analytics.refresh_token_source: per_integration` |
| P5 | Workspace table ready | Columns match sample payload; View ID recorded |
| P6 | Production unchanged | Pin SHA; Zoho admin 404 |

---

## 3. Enable sequence (execution window)

| Step | Action | Rollback if fail |
|------|--------|------------------|
| E1 | Set `ZOHO_ANALYTICS_SYNC_ENABLED=true` on staging only | Revert to `false` |
| E2 | Redeploy / env reload | — |
| E3 | Confirm `integrations.analytics: true` on `/status` | Disable flag |
| E4 | Confirm no other integrations enabled | Disable extras |

---

## 4. Validation cases

### V1 — Manual export success

1. `POST /api/admin/integrations/zoho/sync`  
   Body: `{"integration":"analytics","operation":"export_aggregates","payload":{}}`  
   **or** `POST /api/admin/jobs/run` with `job: zoho_analytics_export`
2. Expect HTTP 200 with `status: success` (or job result with sync success)
3. Confirm Zoho Analytics table has new row
4. Confirm sync run in `GET /api/admin/integrations/zoho/sync-runs?integration=analytics`

### V2 — OAuth health

1. `oauth.by_integration.analytics.oauth_status` → `healthy` or `awaiting_refresh` then `healthy`
2. `authentication_failures` remains 0 after success
3. Cache id `zoho_oauth_access_token_analytics` used (no CRM cache pollution)

### V3 — PII gate (negative)

1. Do **not** inject PII in production path; rely on unit coverage of `is_aggregate_export_safe`
2. Confirm live payload keys ⊆ aggregate allow-list (inspect sync metadata if present — no secrets)

### V4 — Missing workspace (optional negative)

1. Temporarily unset workspace id → expect `SKIPPED` / workspace not configured  
2. Restore workspace id

### V5 — Kill switch

1. `ZOHO_KILL_SWITCH=true` → export skipped / disabled overall  
2. Restore kill switch

### V6 — Isolation

1. CRM / Books / Campaigns / Sign / WorkDrive remain `false`
2. No cron jobs for Zoho appear in scheduler
3. Production SHA and Zoho inactivity unchanged

---

## 5. Observability checklist

| Surface | What to record |
|---------|----------------|
| Admin `/status` | Flag, OAuth analytics row, overall_status |
| Sync runs | sync_id, status, message |
| Audit logs | `ZOHO_SYNC` analytics event |
| Health summary | `zoho_integration_health` |
| Control Centre | No Zoho degraded alert on success |
| Queue / dead letter | Prefer 0 new unresolved on success |

---

## 6. Pass / fail criteria

| Verdict | Definition |
|---------|------------|
| **PHASE_B_LIVE_PASS** | V1 success + V2 healthy + V5 kill switch works + V6 isolation |
| **PHASE_B_LIVE_PASS_WITH_CONDITIONS** | Export works; non-blocking observability gaps documented |
| **PHASE_B_LIVE_FAIL** | Export fails, PII risk, production impact, or other integrations activated |

On **FAIL:** disable `ZOHO_ANALYTICS_SYNC_ENABLED` immediately; do not proceed to Phase C.

---

## 7. Evidence pack (after live run)

Produce:

- `PHASE_B_LIVE_VALIDATION_REPORT.md`
- `PHASE_B_LIVE_VALIDATION.json`

Include: staging SHA, sync_id, HTTP outcomes, OAuth status, kill-switch proof, production isolation.

---

## 8. Explicit non-goals for Phase B

- No CRM sync
- No Books / Campaigns / Sign / WorkDrive
- No scheduler cron
- No production secrets or flags
- No redesign of OAuth architecture

---

## 9. Ready-to-execute statement

This plan is ready when the readiness checklist is fully ticked and programme lead authorises enabling `ZOHO_ANALYTICS_SYNC_ENABLED`. Until then, the Analytics flag must remain **false**.
