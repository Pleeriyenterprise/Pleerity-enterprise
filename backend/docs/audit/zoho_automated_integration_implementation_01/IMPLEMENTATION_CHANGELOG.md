# Zoho Integration Hardening — Implementation Changelog

**Programme:** ZOHO INTEGRATION REFINEMENT — PRE-PRODUCTION ARCHITECTURE HARDENING  
**Date:** 2026-07-09  
**Backlog items:** H-01, H-02, H-03 + version metadata on sync runs + platform observability integration

---

## Summary

Targeted hardening of the existing Zoho integration layer. No feature flags enabled. No OAuth credentials. No staging/production config changes. No cron wiring.

---

## Files added

| File | Purpose |
|------|---------|
| `services/integrations/zoho/version.py` | Layer/adapter/mapping/payload version constants |
| `services/integrations/zoho/operational_health.py` | Operational snapshot + health summary (recalc-queue pattern) |
| `tests/integrations/zoho/test_zoho_operational_health.py` | H-02/H-03/version/observability tests |

---

## Files modified

| File | Change |
|------|--------|
| `services/control_centre_outcome_aggregation.py` | **H-01:** Zoho jobs + `operational_evidence_maintenance_job` in outcome family map and allowlist |
| `services/integrations/zoho/config.py` | **H-02:** Version metadata on status; async `integration_status_snapshot_with_health()` |
| `services/integrations/zoho/registry.py` | **H-03:** `total_leads_count`, `export_type`, `payload_version` in `ANALYTICS_EXPORT_METRICS` |
| `services/integrations/zoho/sync_store.py` | Version block on `zoho_sync_runs` create |
| `services/integrations/zoho/metrics/analytics_export.py` | `payload_version` on export payload |
| `services/integrations/zoho/circuit_breaker.py` | `snapshot()` for operational visibility |
| `routes/integrations/zoho/admin.py` | `/status` returns operational health |
| `routes/observability.py` | `zoho_integration_health` + `integrations.zoho` in health summary; degraded hook |
| `services/control_centre_service.py` | Platform Status `system.integrations.zoho`; automation block; degraded alert |
| `tests/integrations/zoho/test_zoho_integration.py` | Assert layer version on flag snapshot |

---

## Backlog mapping

| ID | Delivered |
|----|-----------|
| **H-01** | Four Zoho manual jobs in `REGISTRY_JOB_OUTCOME_FAMILY` (`platform_other`) and `INTENTIONAL_PLATFORM_OTHER_JOB_IDS` |
| **H-02** | `ZOHO_INTEGRATION_LAYER_VERSION` (`1.0.0`) on admin `/status` and platform health payloads |
| **H-03** | Analytics registry aligned with runtime export (`total_leads_count`, `export_type`, `payload_version`) |
| **Version metadata** | `versions` object on each `zoho_sync_runs` document |
| **Observability** | Integrated via `build_health_summary_payload()` and `get_control_centre_snapshot()` — no new dashboard |

---

## Platform observability integration

| Surface | Field / behaviour |
|---------|-------------------|
| **System Health** | `GET /api/admin/observability/health-summary` → `zoho_integration_health`, `integrations.zoho` |
| **Platform Status** | Control Centre snapshot → `system.integrations.zoho`, `automation.zoho_integration_health` |
| **Automation Control Centre** | Zoho jobs visible in framework audit via existing `JOB_RUNNERS` inventory; health from shared health summary |
| **Incidents / alerts** | Control Centre alert `integrations:zoho_degraded` when layer enabled and degraded |
| **Admin Zoho API** | `GET /api/admin/integrations/zoho/status` → flags + versions + `operational_health` + full snapshot |

When `ZOHO_INTEGRATION_ENABLED=false`, overall status is **`dormant`** — does not degrade platform health.

---

## Governance preserved

- All feature flags default `false`
- Kill switch unchanged
- SoR boundaries unchanged
- No OAuth secrets added
- No scheduler cron for Zoho jobs
- Manual-only job classification explicit in health payload

---

## Additional fix (governance alignment)

`operational_evidence_maintenance_job` was missing from `REGISTRY_JOB_OUTCOME_FAMILY` (pre-existing CI gap). Added as `platform_other` with allowlist entry.
