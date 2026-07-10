# Phase A — Operational Readiness (P5)

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION — PHASE A EXECUTION  
**Date:** 2026-07-10  
**Principle:** Operators must not inspect source code to assess Zoho readiness

---

## 1. Operator information map

All information is available through the approved observability framework.

| Operator question | Where to find it | Field(s) |
|-------------------|------------------|----------|
| Is Zoho integration layer active? | Admin status / health summary | `zoho_integration_enabled` |
| Is kill switch engaged? | Admin status / health summary | `kill_switch_active` |
| Is shared OAuth client configured? | Admin status | `shared_oauth_client_configured` |
| Are per-integration credentials ready? | Admin status | `oauth_by_integration.{name}.credentials_configured` |
| Which refresh token source is in use? | Admin status | `oauth_by_integration.{name}.refresh_token_source` |
| Is legacy fallback in use? | Admin status | `oauth_by_integration.{name}.using_legacy_fallback` |
| Is OAuth healthy for an integration? | Operational snapshot | `oauth.by_integration.{name}.oauth_status` |
| Authentication failures? | Operational snapshot | `oauth.by_integration.{name}.authentication_failures` |
| Last successful refresh? | Operational snapshot | `oauth.by_integration.{name}.last_successful_refresh` |
| Token expiry? | Operational snapshot | `oauth.by_integration.{name}.token_expiry` |
| Expected scope for integration? | Admin status / registry | `expected_scope`, `oauth.credential_registry` |
| Which integrations are enabled? | Admin status | `integrations.{name}` |
| Which integrations are dormant? | Admin status | `integrations.{name}: false` |
| Overall Zoho health? | Health summary | `zoho_integration_health.overall_status` |
| Integration layer version? | Admin status | `integration_layer_version` |
| Queue depth / dead letters? | Operational snapshot | `queue`, `dead_letter` |
| Circuit breaker state? | Operational snapshot | `circuit_breakers` |
| Migration warnings? | Application logs | `deprecated legacy ZOHO_REFRESH_TOKEN` + `using_legacy_fallback` in status |

---

## 2. Observability endpoints

| Surface | Path | Access |
|---------|------|--------|
| **Zoho admin status** | `GET /api/admin/integrations/zoho/status` | Admin JWT; requires `ZOHO_INTEGRATION_ENABLED=true` |
| **System health summary** | `GET /api/admin/observability/health-summary` | Admin JWT; Zoho section always present |
| **Control Centre** | Platform Status UI | `integrations.zoho`, `automation.zoho_integration_health` |

---

## 3. Status value reference

### `overall_status`

| Value | Meaning |
|-------|---------|
| `dormant` | `ZOHO_INTEGRATION_ENABLED=false` |
| `disabled` | Kill switch active |
| `healthy` | Master on; no degradation signals |
| `degraded` | Enabled integration has OAuth/sync/circuit-breaker issues |

**Phase A expectation:** `healthy` (all integrations dormant).

### Per-integration `oauth_status`

| Value | Meaning |
|-------|---------|
| `not_configured` | Missing client or refresh token |
| `awaiting_refresh` | Credentials OK; no cached access token yet |
| `healthy` | Cached access token valid |
| `cached_expired` | Cache exists but expired |
| `authentication_failed` | Refresh failures recorded |
| `not_applicable` | Sign (webhook-only) |

---

## 4. Phase A operator checklist

| # | Check | Pass criterion |
|---|-------|----------------|
| 1 | Master flag on | `zoho_integration_enabled: true` |
| 2 | Kill switch off | `kill_switch_active: false` |
| 3 | OAuth client configured | `shared_oauth_client_configured: true` |
| 4 | All integrations dormant | All `integrations.*: false` |
| 5 | Overall healthy | `operational_health.overall_status: healthy` |
| 6 | Version visible | `integration_layer_version: 1.0.0` |
| 7 | Registry visible | `operational_snapshot.oauth.credential_registry` present |
| 8 | No unexpected sync runs | `sync-runs` empty or historical only |
| 9 | Platform health unaffected | System health not `critical` due to Zoho |

---

## 5. Phase A webhook surface note

When `ZOHO_INTEGRATION_ENABLED=true`, webhook routes are **reachable** (no longer 404). They remain HMAC-protected:

- Without webhook secrets → `401 Unauthorized`
- With secrets but integration flag off → handler returns `accepted: false` with reason (e.g. `sign_sync_disabled`)

This is expected. Webhook secrets are not required for Phase A shell validation.

---

## 6. Kill switch procedure

| Action | Effect |
|--------|--------|
| Set `ZOHO_KILL_SWITCH=true` | All integrations immediately disabled; `overall_status: disabled` |
| Redeploy or env reload | Immediate effect on next request |

---

## 7. Secrets policy

- No secrets appear in any API response
- Refresh token presence indicated by boolean flags only
- Render dashboard is sole secret store

---

## 8. Operator readiness verdict

**READY** — all required operator information exists in the approved observability framework without code inspection.
