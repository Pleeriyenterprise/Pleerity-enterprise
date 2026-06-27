# Observability Improvements Introduced

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

---

## Code improvements

1. **`_fetch_jobs_detail_for_health_summary`** — structured batch fetch with documented 4-query pattern
2. **Registry completeness** — all jobs expose `schedule`, `critical`, `max_delay_minutes`, `frequency_label` in health payload
3. **Outcome family map** — complete, alphabetically sorted, CI-enforced

---

## Audit artefacts added

| Artefact | Purpose |
|---|---|
| `JOB_INVENTORY.json` | Machine-readable 51-job catalogue |
| `RUNTIME_VERIFICATION.json` | Staging probe results |
| `tmp_operational_reliability_staging_audit_01.py` | Repeatable staging validation script |

---

## Existing observability strengths confirmed

| Surface | Authority source |
|---|---|
| Automation Control Centre job runs | `job_runs` collection |
| System Health job states | `job_runs` + registry + heartbeat |
| Recalc queue panel | `compliance_recalc_operational_snapshot` |
| Scheduler registration count | In-process APScheduler introspection |
| Observability DB name exposed | Prevents cross-DB drift confusion |

---

## Gaps identified (not yet fixed)

| Gap | Recommendation |
|---|---|
| No Prometheus/Datadog export | Accept Mongo+REST for now; add metrics endpoint later |
| Health summary had no latency telemetry | Log duration after batching deploy |
| Control Centre error opaque (500) | Structured error logging per collector |

---

## False-healthy observability review

| Indicator | Can lie? | Guard |
|---|---|---|
| `overall_health=healthy` | No if heartbeat stale or critical missed | Strict `_compute_overall_health` |
| `conditional_no_output` | No — explicitly labeled, not "healthy" | JOB_STATE_CONDITIONAL_NO_OUTPUT |
| Zero queue depth | No — could mean idle OR worker down | Heartbeat + worker last_run |
| Open incidents = 0 | Only if genuinely resolved | Fingerprint dedupe, not suppression |
