# CRM_LIVE_STAGING_VALIDATION

**Phase:** `PHASE_C_ZOHO_CRM_IMPLEMENTATION_01`  
**Date:** 2026-07-14  
**Status:** PENDING STAGING EXECUTION

Follow Analytics staged lifecycle. Do **not** fabricate Zoho success.

## C11 — Configuration only (`ZOHO_CRM_SYNC_ENABLED=false`)

| Step | Expected | Result |
|---|---|---|
| Staging healthy | Deploy green; System Health reachable | ☐ |
| Status snapshot | `crm_ops` / `crm_target` present; flag false | ☐ |
| OAuth registry | CRM refresh configured; expected scope includes READ | ☐ |
| No live CRM writes | No successful CRM create while flag false | ☐ |
| Production unchanged | Prod CRM still disabled / unregistered | ☐ |

## C12 — One controlled manual sync

Prerequisites: C11 PASS; refresh token includes READ; sandbox custom fields exist.

1. Set `ZOHO_CRM_SYNC_ENABLED=true` on **staging only**
2. Choose one known Pleerity staging lead with email + last_name
3. Manual sync once: admin Zoho sync `crm` / `upsert_lead` `{ "lead_id": "..." }` — **do not auto-retry**
4. Validate checklist:

| Check | Result |
|---|---|
| OAuth refresh / access token | ☐ |
| Payload validation passed | ☐ |
| Create or update Lead in Zoho | ☐ |
| External ID stored in `zoho_external_keys` | ☐ |
| Audit evidence present | ☐ |
| Sync history SUCCESS with `external_id` | ☐ |
| Queue behaviour sane | ☐ |
| Soft fail → DL path verified separately if needed | ☐ |
| Replay capability known | ☐ |
| System Health `crm_ops` updated | ☐ |
| Control Centre no false incident | ☐ |
| No duplicate Zoho leads for same `Pleerity_Lead_ID` | ☐ |
| Production unchanged | ☐ |

## C13 — Hardening gate

Complete `CRM_OPERATIONAL_HARDENING_REPORT.md` before any schedule discussion. CRM remains **manual-only**.
