# Phase A — Runtime Validation (P3 + P4)

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION — PHASE A EXECUTION  
**Date:** 2026-07-10  
**Validation type:** Automated (local) + documented live protocol (staging)

---

## 1. Credential scenario matrix (P3)

All scenarios validated via unit tests unless marked **LIVE**.

| Scenario | Configuration | Expected runtime behaviour | Observable via |
|----------|---------------|---------------------------|----------------|
| **No credentials** | No `ZOHO_CLIENT_*`, no refresh tokens | `credentials_configured: false`; sync → `no_credentials` skip when integration enabled | `/status` → `oauth_by_integration.*.credentials_configured` |
| **Partial — client ID only** | `ZOHO_CLIENT_ID` set, no secret | `shared_oauth_client_configured: false`; `credentials_configured: false` | `/status`, resolver unit tests |
| **Partial — client pair, no refresh** | Client ID + secret, no refresh tokens | `shared_oauth_client_configured: true`; per-integration `refresh_token_source: none` | `/status` → Phase A default |
| **Complete — per-integration token** | Client pair + `ZOHO_CRM_REFRESH_TOKEN` | `credentials_configured: true` for CRM; `oauth_status: awaiting_refresh` until first API call | `/status` → `oauth.by_integration.crm` |
| **Complete — legacy fallback** | Client pair + `ZOHO_REFRESH_TOKEN` | CRM: no warning; others: log warning + `using_legacy_fallback: true` | Logs + `/status` |
| **Expired access token** | Valid refresh; Mongo `expires_at` in past | Next `get_access_token()` triggers refresh | `oauth_status: cached_expired` then refresh |
| **Invalid refresh token** | Bad refresh token value | Refresh returns non-200; `auth_failure_count` increments | `oauth_status: authentication_failed` |
| **Invalid client secret** | Wrong `ZOHO_CLIENT_SECRET` | Zoho returns 4xx on refresh | `authentication_failures` ↑, `last_auth_failure_detail` |
| **OAuth refresh failure** | Network/timeout | `auth_failure_count` increments; no access token stored | `operational_snapshot.oauth.by_integration` |
| **Region mismatch** | EU tokens + US endpoints (misconfigured `ZOHO_ACCOUNTS_URL`) | Refresh failure | `authentication_failed` + error log |

**No production credentials used.** Live credential scenarios (invalid token, region mismatch) validated on staging only after secrets are added.

---

## 2. Phase A runtime posture (P4)

**Condition:** `ZOHO_INTEGRATION_ENABLED=true`, all integration flags `false`.

| Requirement | Expected | Test / evidence |
|-------------|----------|-----------------|
| Platform starts successfully | No import/startup errors | Staging `/api/health` → 200 |
| Platform remains healthy | No Zoho-induced crash | Health summary stable |
| OAuth status exposed | `oauth.by_integration` populated | `test_phase_a_oauth_exposes_per_integration_status` |
| Integration health exposed | All `enabled: false` | `test_phase_a_operational_snapshot_healthy_with_no_credentials` |
| Version metadata exposed | `integration_layer_version: 1.0.0` | `integration_status_snapshot()` |
| Dormant integrations reported | `overall_status: healthy` | Operational snapshot test |
| No outbound Zoho API traffic | HTTP client not called | `test_phase_a_manual_sync_skipped_not_outbound` |
| No sync jobs executed | `SKIPPED` / `DISABLED` | Service + enqueue tests |
| Platform health preserved | Zoho dormant does not block health | Observability integration test |
| No scheduler cron | No Zoho scheduler wiring | Code audit — no matches |

---

## 3. Live staging validation protocol

Execute after Phase A Render configuration is applied.

### Pre-flight

```bash
# Confirm deploy SHA
curl -s https://pleerity-enterprise.onrender.com/api/health
```

### Admin status (requires admin JWT)

```
GET https://pleerity-enterprise.onrender.com/api/admin/integrations/zoho/status
```

**Expected Phase A response fields:**

```json
{
  "zoho_integration_enabled": true,
  "kill_switch_active": false,
  "shared_oauth_client_configured": true,
  "credentials_configured": false,
  "integrations": {
    "analytics": false,
    "crm": false,
    "campaigns": false,
    "sign": false,
    "books": false,
    "workdrive": false
  },
  "operational_health": {
    "overall_status": "healthy"
  }
}
```

(`credentials_configured` is `true` only if a refresh token is also present.)

### Platform health summary

```
GET /api/admin/observability/health-summary
```

Confirm `zoho_integration_health.overall_status` is `healthy` (not `dormant`).

### Negative checks

| Check | Expected |
|-------|----------|
| Webhook without secret | `401` (not 404) |
| Admin status with master off | `404` |
| Manual sync CRM (flag off) | `SKIPPED` / `DISABLED` |

---

## 4. OAuth refresh timing

OAuth refresh is **lazy**:

- Not triggered on application startup
- Not triggered by health endpoints
- Triggered only when an enabled integration calls `ZohoHttpClient.request()`

Phase A with all integration flags off → **no OAuth refresh occurs**.

---

## 5. Test results

```
pytest tests/integrations/zoho/ -q
47 passed (includes 10 Phase A tests)
```

---

## 6. Live validation status

| Item | Status |
|------|--------|
| Local automated validation | **COMPLETE** |
| Staging live Phase A (master flag on) | **PENDING** — requires operator to set `ZOHO_INTEGRATION_ENABLED=true` + OAuth secrets |
