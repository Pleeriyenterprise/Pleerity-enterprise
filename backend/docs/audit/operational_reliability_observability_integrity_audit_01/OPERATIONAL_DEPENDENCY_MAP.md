# Operational Dependency Map

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

```mermaid
flowchart TB
  subgraph scheduler [Scheduler Layer]
    APS[APScheduler server.py]
    HB[scheduler_heartbeat job]
    SR[startup_reconciliation]
  end

  subgraph execution [Execution Layer]
    JR[job_runner.run_instrumented]
    CRW[compliance_recalc_worker]
    NRW[notification_retry_worker]
    RRW[risk_signal_regen_worker]
  end

  subgraph persistence [Persistence Layer]
    JRDB[(job_runs)]
    CRQ[(compliance_recalc_queue)]
    NRQ[(notification_retry_queue)]
    RRGQ[(risk_signal_regen_queue)]
    SHB[(scheduler_heartbeat)]
    INC[(incidents)]
    ML[(message_logs)]
  end

  subgraph monitors [Monitoring Layer]
    SW[sla_watchdog]
    CSM[compliance_sla_monitor]
    NFS[notification_failure_spike_monitor]
    DR[delivery_reconciliation]
    RRAM[risk_signal_regen_alert_monitor]
  end

  subgraph surfaces [Admin Surfaces]
    HS[System Health]
    ACC[Automation Control Centre]
    PS[Platform Status]
    INCP[Incidents Page]
  end

  subgraph customer [Customer Impact Path]
    ENQ[enqueue_compliance_recalc]
    REC[recalculate_and_persist]
    SC[compliance scores]
    REM[reminders / reports]
  end

  APS --> JR
  APS --> HB
  SR --> JR
  JR --> JRDB
  JR --> CRW
  CRW --> CRQ
  CRW --> ENQ
  ENQ --> REC
  REC --> SC
  JR --> REM
  JR --> ML
  SW --> INC
  SW --> JRDB
  CSM --> INC
  RRAM --> INC
  HB --> SHB
  DR --> JRDB
  JRDB --> HS
  SHB --> HS
  INC --> HS
  HS --> PS
  INC --> INCP
  JRDB --> ACC
```

---

## Critical path: compliance score freshness

```
Property mutation / sync
  → compliance_recalc_queue (PENDING)
  → compliance_recalc_worker (15s)
  → recalculate_and_persist
  → automation_status.last_score_recalc_at
  → client dashboard / reports
```

**Failure modes:** stuck RUNNING (reclaim), DEAD rows (SLA monitor), worker down (heartbeat + missed job state).

---

## Critical path: operational truth to UI

```
job_runs (authoritative execution)
  + scheduler_heartbeat (liveness)
  + incidents (open faults)
  → build_health_summary_payload()
  → System Health job_states + overall_health
  → get_control_centre_snapshot()
  → Platform Status scores + alerts
```

**Drift risk:** Jobs scheduled but absent from `job_schedule_registry` → invisible to health/SLA (remediated in this audit).

---

## Notification / alert path

```
Monitor detects fault
  → record_operational_detection (fingerprint dedupe)
  → incidents collection (OPEN)
  → INTERNAL_ALERT email (suppression window)
  → Recovery detected on next successful run
  → incident_recovery auto-resolve
```

**Anti-flood:** fingerprint dedupe, severity suppression windows, flap protection, deploy suppression.

---

## External dependencies

| Dependency | Impact if unavailable |
|---|---|
| MongoDB | All queues, job_runs, incidents halt; API readiness degrades |
| Render web process | Scheduler stops; heartbeat goes stale |
| Postmark | message_logs FAILED; spike monitor may fire |
| Stripe webhooks | Billing reconcile jobs degrade; not compliance timeline |

---

## Registry alignment (post-remediation)

| Set | Count | Must match |
|---|---|---|
| `server.py` scheduled ids | 51 | ✓ |
| `JOB_RUNNERS` | 51 | ✓ |
| `CRITICAL_JOB_REGISTRY` | 51 | ✓ (was 48) |
| `REGISTRY_JOB_OUTCOME_FAMILY` | 51 | ✓ (was 49) |
