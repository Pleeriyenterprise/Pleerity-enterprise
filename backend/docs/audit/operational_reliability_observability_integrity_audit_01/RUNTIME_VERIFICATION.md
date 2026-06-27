# Runtime Verification Results

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01  
**Environment:** Staging  
**Artefact:** `RUNTIME_VERIFICATION.json`  
**Validated:** 2026-06-27 (pre-remediation deploy)

---

## API probes

| Probe | Result |
|---|---|
| `/api/health` | healthy, staging, ready |
| `/api/version` | `2d64104e` |
| Admin login | Success |
| `/admin/observability/health-summary` | 200 — **55s latency** |
| `/admin/control-centre/snapshot` | **500** — Internal server error |
| `/admin/observability/incidents?status=open` | 200 — 4 open P2 items |
| `/admin/observability/job-runs` | 200 |

---

## Scheduler / heartbeat

| Check | Result |
|---|---|
| `scheduler_runtime.available` | true |
| `registered_jobs_count` | 51 |
| `heartbeat_stale` | false |
| `last_heartbeat_at` | Fresh (< 5 min) |

---

## Queue health (recalc)

| Metric | Value |
|---|---|
| pending | 0 |
| running | 0 |
| dead_letter | 0 |
| stuck_running | 0 |
| posture | NON_BLOCKING_OBSERVABILITY_ONLY |

---

## Health summary (pre-remediation)

| Metric | Value |
|---|---|
| `overall_health` | degraded |
| Jobs in health summary | **48** (3 missing from registry) |
| Job states | 36 conditional_no_output, 10 healthy, 1 degraded, 1 missed |
| Open incidents (health payload) | 4 |
| `delivery_unknown_stale` | 20 |
| Critical missed | 0 |
| Failed 24h | 0 |

---

## Open incidents (sample)

`activation_reminder_processing` — missed SLA (420 min window, last success 06:40 UTC, detected 13:50 UTC). **Genuine operational incident** — not false positive.

---

## Post-remediation revalidation required

After staging deploy of registry + health batching fixes:

1. Confirm `jobs_in_health_summary` = 51
2. Confirm health-summary latency < 10s
3. Confirm control-centre/snapshot returns 200
4. Re-run `tmp_operational_reliability_staging_audit_01.py`

---

## Runtime verification verdict (pre-deploy)

**FAIL** — Platform Status unavailable (500); health registry incomplete; health summary too slow for operational use.
