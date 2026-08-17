# Phase A — Live Sandbox Validation Report

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION — PHASE A EXECUTION  
**Date:** 2026-07-10  
**Staging API:** `https://pleerity-enterprise.onrender.com/api`  
**Production API:** `https://api.pleerityenterprise.co.uk/api`  
**Deployed SHA:** `15dc0a7afa0742fbe356e1faf0f6565f3700a7b0`  
**origin/develop HEAD:** `15dc0a7afa0742fbe356e1faf0f6565f3700a7b0`

---

## Final verdict

# **PHASE_A_LIVE_PASS**

**13 / 13 checks passed.** Phase A live sandbox validation succeeded. **Do not proceed to Analytics (Phase B)** until governance explicitly authorises the next phase gate.

---

## Executive summary

Staging has converged on commit `15dc0a7a` with `ZOHO_INTEGRATION_ENABLED=true` and all per-integration flags disabled. The master integration layer is healthy, OAuth client credentials are configured, no refresh tokens are active, no outbound Zoho API activity occurred, webhooks reject unsigned requests, production remains isolated, and observability surfaces Zoho as enabled-but-dormant.

---

## 1. Deployment

| Check | Result | Evidence |
|-------|--------|----------|
| origin/develop matches staging SHA | **PASS** | `/api/version` → `15dc0a7afa0742fbe356e1faf0f6565f3700a7b0` |
| Staging health | **PASS** | `/api/health` → `status: healthy` |
| Readiness degraded | **PASS** | `readiness.degraded: false`, `stage: ready` |

---

## 2. Phase A configuration (live)

Inferred from authenticated `GET /api/admin/integrations/zoho/status`:

| Setting | Live value | Expected | Result |
|---------|------------|----------|--------|
| `ZOHO_INTEGRATION_ENABLED` | `true` | `true` | **PASS** |
| `ZOHO_ENVIRONMENT` | `staging` (via `/api/version`) | `staging` | **PASS** |
| `ZOHO_KILL_SWITCH` | `false` | `false` | **PASS** |
| Per-integration flags | All `false` | All `false` | **PASS** |
| Legacy `ZOHO_REFRESH_TOKEN` | `legacy_refresh_token_configured: false` | Not relied upon | **PASS** |
| Per-integration refresh tokens | All `refresh_token_source: none` | Not required for Phase A shell | **PASS** |
| Shared OAuth client | `shared_oauth_client_configured: true` | Configured | **PASS** |
| Production Zoho active | Admin status `404` | Not active | **PASS** |

---

## 3. Admin status

**Endpoint:** `GET /api/admin/integrations/zoho/status`  
**HTTP:** 200

| Field | Value |
|-------|-------|
| `integration_layer_version` | `1.0.0` |
| `zoho_integration_enabled` | `true` |
| `kill_switch_active` | `false` |
| `integrations.*` | All `false` |
| `shared_oauth_client_configured` | `true` |
| `credentials_configured` | `false` (no refresh tokens — expected for Phase A shell) |
| `overall_status` | `healthy` |
| Secrets exposed | **None** |

---

## 4. Outbound activity

| Metric | Value | Result |
|--------|-------|--------|
| Queue pending | 0 | **PASS** |
| Queue processing | 0 | **PASS** |
| Dead letters unresolved | 0 | **PASS** |
| Integration `enabled` | All `false` | **PASS** |
| `last_success_at` | All `null` | **PASS** |
| `manual_jobs_only` | `true` | **PASS** |
| Outbound Zoho API calls | None triggered | **PASS** |

No sync jobs were executed during validation. No manual Zoho jobs were triggered.

---

## 5. Webhook security

With master flag enabled, unsigned webhooks return **401** (HMAC gate before handler):

| Webhook | HTTP |
|---------|------|
| CRM | 401 |
| Books | 401 |
| Sign | 401 |
| Campaigns | 401 |

**Signed inbound-forbidden (CRM/Books):** Live test skipped — webhook secrets not present in validation environment. Behaviour covered by committed unit tests (`test_zoho_integration.py`: signed CRM/Books return `accepted: false` with inbound-forbidden reason). Unsigned rejection proves webhooks cannot modify authoritative state without valid HMAC.

---

## 6. Observability

| Surface | Result | Key fields |
|---------|--------|------------|
| System Health (`/api/admin/observability/health-summary`) | **PASS** | `zoho_integration_health.overall_status: healthy`, `zoho_integration_enabled: true`, `manual_jobs_only: true` |
| Control Centre (`/api/admin/control-centre/snapshot`) | **PASS** | `automation.zoho_integration_health` + `system.integrations.zoho` both healthy |
| Zoho incident raised | **None** | No `integrations:zoho_degraded` alert (requires `overall_status: degraded`) |
| Kill switch visible | **PASS** | `kill_switch_active: false` in all surfaces |

**Note:** Platform `overall_health` is `attention_required` due to unrelated platform signals — Zoho-specific health is `healthy` and does not degrade automation.

---

## 7. Production isolation

| Check | Result | Evidence |
|-------|--------|----------|
| Production SHA unchanged | **PASS** | `89217062481b4eb858a8b530ec90c83de067a4be` |
| Production health | **PASS** | `healthy`, `degraded: false` |
| Production Zoho status | **PASS** | `404` (master flag off) |
| Production sync activity | **PASS** | No production validation calls made |

---

## 8. Constraints confirmation

| Constraint | Honoured |
|------------|----------|
| Analytics / CRM / Books / Campaigns / Sign / WorkDrive enabled | **No** |
| Sync jobs run | **No** |
| Cron wired | **No** |
| Production modified | **No** |
| Manual jobs triggered | **No** |

---

## 9. Conditions and notes

| Item | Note |
|------|------|
| Per-integration refresh tokens | Not configured on staging — correct for Phase A shell; required at Phase B+ |
| OAuth token refresh | Not exercised (no integration flags, no API calls) |
| Signed webhook inbound-forbidden | Unit-test evidence only (no webhook secrets in validation env) |
| Platform `attention_required` | Unrelated to Zoho; Zoho subsection is `healthy` |

---

## 10. Next phase gate

**Phase A live validation is complete.** Phase B (Analytics) requires governance approval plus:

1. `ZOHO_ANALYTICS_REFRESH_TOKEN` in Render staging secrets  
2. `ZOHO_ANALYTICS_WORKSPACE_ID` configured  
3. `ZOHO_ANALYTICS_SYNC_ENABLED=true`  
4. Separate Analytics live validation protocol  

---

## 11. Evidence artefacts

| File | Purpose |
|------|---------|
| `PHASE_A_LIVE_VALIDATION.json` | Machine-readable check results |
| `tmp_phase_a_live_validation_execute.py` | Validation runner (local, not committed) |

**Validation executed:** 2026-07-10T08:22:47Z
