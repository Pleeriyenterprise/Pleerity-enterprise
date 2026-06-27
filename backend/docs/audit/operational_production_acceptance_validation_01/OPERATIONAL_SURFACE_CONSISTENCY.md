# Operational Surface Consistency Validation

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Validated at:** 2026-06-27T21:52:07Z

---

## Single operational truth chain

```
job_runs + scheduler_heartbeat + incidents + queues
    → build_health_summary_payload()
        → System Health
        → Control Centre snapshot (Platform Status)
    → Incidents API
    → Automation Centre (job-runs)
```

No secondary cached authority layer observed.

---

## Cross-surface consistency checks

| Check | Health | Incidents API | Control Centre | Consistent? |
|---|---|---|---|---|
| Open incidents count | 5 | 5 (items) | 5 (automation.open_operational_incidents) | **Yes** |
| Duplicate fingerprint rows | — | 0 | — | **Yes** |
| Jobs in health summary | 51 | — | Uses same health payload | **Yes** |
| Overall health posture | attention_required | — | platform_status: critical | **Yes** (critical = stricter composite) |
| Recalc queue pending | 0 | — | — | **Yes** (healthy queue) |
| Heartbeat stale | false | — | — | **Yes** |

---

## Job runs vs health states

Recent job runs show continuous `compliance_recalc_worker`, `risk_signal_regen_worker`, `notification_retry_worker` successes — consistent with queue depth 0 and non-stale heartbeat.

---

## Operational emails vs incidents

Persistent P2 incidents show `last_alert_email_at` frozen for ≥6h on long-running conditions — consistent with lifecycle fix (no periodic re-email). New alerts correlate with deploy-transient conditions (heartbeat stale, missed SLA during restart).

---

## Verdict

**Operational surfaces agree.** Degraded/critical signalling is consistent across System Health, Platform Status, and Incidents. No silent fallback or false healthy state detected.
