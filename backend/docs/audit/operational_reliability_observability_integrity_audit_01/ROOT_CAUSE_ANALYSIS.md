# Root Cause Analysis

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01  
**Environment:** Staging (production-equivalent)

---

## Issue 1 — Health registry blind spot (P1 operational)

| Field | Detail |
|---|---|
| **Symptom** | 3 scheduled jobs executed but absent from System Health / SLA watchdog metadata |
| **Jobs** | `commercial_entitlement_expiry`, `scheduled_admin_communications`, `work_order_schedule_reminders` |
| **Root cause** | Jobs added to `server.py` + `JOB_RUNNERS` without updating `job_schedule_registry.CRITICAL_JOB_REGISTRY` |
| **Impact** | Missed SLA not detected; jobs invisible on health dashboard; false confidence in automation coverage |
| **Customer impact** | Indirect — entitlement expiry or admin comms failures could go undetected longer |
| **Remediation** | Added registry entries (see REMEDIATIONS_IMPLEMENTED.md) |

---

## Issue 2 — Platform Status outcome-family drift (P2 governance)

| Field | Detail |
|---|---|
| **Symptom** | CI test `test_registry_and_runners_exactly_match_explicit_family_map` failing |
| **Missing keys** | `commercial_entitlement_expiry`, `rent_operations_daily_job` |
| **Root cause** | Outcome family map not updated when jobs were introduced |
| **Impact** | Platform Status 24h outcome aggregation mis-buckets job metrics into `platform_other` |
| **Remediation** | Added keys; alphabetically sorted map |

---

## Issue 3 — Health summary latency / Platform Status 500 (P0 operational)

| Field | Detail |
|---|---|
| **Symptom** | `GET /health-summary` ~55s; `GET /control-centre/snapshot` HTTP 500 after ~69s |
| **Root cause** | N+1 Mongo pattern: 4 `find_one` queries × 48–51 jobs ≈ **200 sequential queries** per health build; Control Centre chains health + revenue + drift scans |
| **Impact** | Platform Status unavailable; operators cannot trust real-time dashboard; possible gateway timeout |
| **Remediation** | Replaced with 4 aggregation pipelines (`_fetch_jobs_detail_for_health_summary`) |
| **Revalidation** | Requires staging redeploy |

---

## Issue 4 — Legitimate degraded health (not a defect)

| Field | Detail |
|---|---|
| **Symptom** | `overall_health=degraded`, 4 open incidents, `delivery_unknown_stale=20` |
| **Root cause** | Real operational conditions: `activation_reminder_processing` missed 420 min SLA; 20 reconciliation job runs with stale `delivery_unknown` metrics |
| **Impact** | Correct — monitoring is **not** falsely healthy |
| **Action** | Investigate activation reminder schedule/data; run delivery reconciliation or acknowledge stale rows |

---

## Issue 5 — Incident API response shape (P3 documentation)

| Field | Detail |
|---|---|
| **Symptom** | Audit script reported 0 open incidents while health summary reported 4 |
| **Root cause** | Incidents list API returns `{items: [...]}` not bare list |
| **Impact** | Integration/audit tooling only — platform UI uses correct client |
| **Remediation** | Documented; audit script corrected |

---

## Issue 6 — False-healthy patterns reviewed (no code defect found)

| Pattern | Guard |
|---|---|
| Empty query → "healthy" | Jobs use `OUTCOME_CONDITIONAL_NO_OUTPUT` state, not `healthy` |
| Worker crash | Heartbeat stale → `overall_health` failed/degraded; P1 incident |
| Silent exception in job | `run_instrumented` records FAILED in `job_runs` |
| Suppressed monitoring | No hardcoded healthy states found in health builder |
| Cache stale health | Health summary is on-demand from Mongo — no stale cache layer |

---

## Issue 7 — Registry alignment tests skipped in CI

| Field | Detail |
|---|---|
| **Symptom** | `test_automation_registry_alignment` marked skip in conftest |
| **Root cause** | Legacy skip marker for integration suite |
| **Impact** | Registry drift reached staging undetected |
| **Recommendation** | Un-skip registry alignment tests in CI (manual follow-up)
