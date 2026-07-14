# Analytics Operational Hardening Report

**Programme:** PHASE_B_ANALYTICS_OPERATIONAL_HARDENING_01  
**Date (UTC):** 2026-07-14  
**Baseline:** Phase B live pass + UTC reporting window (`c31046ba` and prior)  
**Mode:** Operational resilience — no architecture redesign  

---

## Executive summary

The Analytics integration remains a **manual, append-only, Option B OAuth** path with proven staging delivery. Hardening adds **deterministic preflight**, **same-period duplicate protection** (with operator override), **result-period persistence**, **soft-failure dead-letter + replay resolve**, and **`analytics_ops` signals** on the existing System Health surface.

**Final platform verdict:** see `ANALYTICS_PRODUCTION_READINESS_REPORT.md` → `ANALYTICS_PRODUCTION_READY_WITH_CONDITIONS`.

---

## Stage findings and actions

### H1 — Export lifecycle

| Area | Pre-hardening | Action |
|------|---------------|--------|
| Manual job / admin sync | Works | Unchanged |
| Kill switch / flags | Early skip | Unchanged (deterministic) |
| Soft Zoho API failure | `FAILED` only — not replayable | **Analytics soft fails → dead letter** |
| Exception path | Already DL | Unchanged |
| Metadata / period on run | Not persisted | **`result_summary` on complete** |
| Cron | Not wired (`manual_jobs_only`) | **Intentionally unchanged** |
| HTTP auto-retry | None (30s timeout) | Documented; no speculative rewrite |
| Cancellation | None | Documented |

Lifecycle remains: disabled/kill → skip; preflight → skip; duplicate → skip; success → SUCCESS; soft fail → DEAD_LETTER; exception → DEAD_LETTER.

### H2 — Duplicate protection

**Finding:** Accidental same-period duplicates were possible (append every run).

**Assessment:** Undesirable for daily aggregate table; legitimate re-export must remain possible.

**Implemented:** Before Zoho POST, skip if a prior `SUCCESS` exists for the same `period_start`/`period_end` in `result_summary`. Override with `force_reexport: true` on the sync/job payload. Append-only Zoho import **unchanged**.

### H3 — Schema validation

**Finding:** Failures previously appeared only as Zoho API errors.

**Implemented (safe/local):**

- Required workspace/view/org presence  
- Numeric ID shape checks  
- HTTPS Analytics API base  
- Required 12-column payload contract  

**Not implemented (conditional):** Live Zoho describe of workspace/view/columns — needs `ZohoAnalytics.metadata.read` (current expected scope is `data.create` only). Operators still get actionable preflight diagnostics without relying on import 4xx/5xx for config drift.

### H4 — Configuration validation

**Implemented:** `analytics_target` on admin `/status` (boolean presence + missing keys + api_base + table name). Config invalid → skip with `CONFIG_INVALID` before HTTP.

### H5 — Payload validation

**Implemented:** `validate_analytics_export_payload()` — required columns, types, `export_type`, `payload_version`, UTC midnight window, one-day span, non-negative counts, PII gate retained.

### H6 — Operational observability

**Implemented:** `analytics_ops` block inside existing `build_zoho_operational_health_summary` (System Health / Control Centre consumers):

- enabled / oauth_status / configuration_complete  
- last success/failure (+ sync ids, error)  
- consecutive failure proxy / 24h failures  
- last success duration  
- current reporting period  
- last exported period  
- `next_expected_export: manual_only_no_cron`  

No parallel monitoring stack.

### H7 — Recovery

| Path | Change |
|------|--------|
| Soft Analytics API fail | Dead-letter + audit |
| Replay success/skip | Marks DL **resolved** |
| Replay failure | Increments `replay_count` |
| Rate limit / timeout | Still client-level; now DL’d for Analytics |

### H8 — Governance

**Confirmed unchanged:** Pleerity SoR; Analytics outbound aggregate only; no inbound Analytics authority; billing/compliance not mutated; flags/kill switch still gate execution.

### H9 — Production readiness

See dedicated readiness report. Continuous unattended production is **conditioned** on remaining manual posture and deferred remote schema probe.

---

## Files touched

| File | Change |
|------|--------|
| `adapters/analytics.py` | Config/payload preflight, duplicate guard, result summary |
| `metrics/analytics_export.py` | Column contract + payload validator |
| `sync_store.py` | `result_summary`, period lookup, DL resolve/replay_count |
| `service.py` | Persist summary; Analytics soft-fail DL; replay resolve |
| `config.py` | `analytics_target_config_snapshot` on status |
| `operational_health.py` | Analytics sync signals + `analytics_ops` |
| `types.py` | `DUPLICATE_PERIOD`, `PAYLOAD_INVALID`, `CONFIG_INVALID` |
| Tests | Import + operational suite updated |

---

## Explicit non-actions

- No cron wiring  
- No Render secret changes  
- No production deploy from this exercise  
- No Zoho Architecture redesign  
- No removal of append-only import  
