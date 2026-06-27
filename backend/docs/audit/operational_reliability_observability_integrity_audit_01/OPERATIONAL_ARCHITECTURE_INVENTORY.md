# Operational Architecture Inventory

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01  
**Environment audited:** Staging (`pleerity-enterprise.onrender.com`) — treated as production  
**Date:** 2026-06-27

---

## Executive summary

The automation platform is a **single-process APScheduler** deployment on Render with **51 scheduled jobs**, MongoDB-backed **work queues**, **`job_runs` observability ledger**, **`incidents` operational engine**, and three admin surfaces (System Health, Automation Control Centre, Platform Status / Control Centre snapshot).

---

## 1. Scheduler (APScheduler)

| Attribute | Detail |
|---|---|
| Location | `backend/server.py` |
| Job store | MongoDB `scheduled_jobs` |
| Timezone | UTC |
| Defaults | `coalesce=True`, `max_instances=1`, `misfire_grace_time=300` |
| Entry point | `job_runner.run_scheduled_job` → `run_instrumented` |
| Heartbeat job | `scheduler_heartbeat` every 2 min → `scheduler_heartbeat` collection |
| Startup recovery | `startup_reconciliation.py` — 6 critical infrequent jobs |
| Render cron | **None** — all scheduling in-process |

---

## 2. Scheduled jobs (51)

See `JOB_INVENTORY.json` for the full machine-readable list.

Categories:

| Category | Count | Examples |
|---|---|---|
| Queue workers (interval) | 2 | `compliance_recalc_worker` (15s), `risk_signal_regen_worker` (30s) |
| Monitoring / watchdog | 8 | `sla_watchdog`, `scheduler_heartbeat`, spike monitors |
| Notifications / delivery | 14 | `daily_reminders`, `scheduled_reports`, digests |
| Compliance batch | 6 | `expiry_rollover_recalc`, score snapshots |
| Billing / subscription | 5 | `subscription_lifecycle`, Stripe reconcile |
| Lead / onboarding | 9 | nurture, follow-up, activation |
| Order / document pipeline | 5 | order delivery, generation retry |
| Work orders | 3 | SLA breach, schedule reminders |
| Client lifecycle | 4 | archive, purge, test-flag |
| Other | 5 | predictive insights, rent ops, pilot reconcile |

---

## 3. Work queues (MongoDB)

| Collection | Service | States | Reclaim / dead-letter |
|---|---|---|---|
| `compliance_recalc_queue` | `compliance_recalc_queue.py` | PENDING, RUNNING, DONE, FAILED, DEAD | Stale RUNNING reclaim (1800s); ≥5 attempts → DEAD |
| `risk_signal_regen_queue` | `risk_signal_regen_queue.py` | Same | Debounce + backoff |
| `notification_retry_queue` | `notification_orchestrator.py` | PENDING+ | Minute worker, 50/batch |
| `onboarding_email_queue` | `onboarding_sequence_service.py` | PENDING, sent | Hourly processor |
| `lead_sequence_state` | `lead_automation_service.py` | active/stopped | Sequence-driven |

---

## 4. Observability ledger

| Collection | Purpose |
|---|---|
| `job_runs` | Every instrumented execution: status, duration, outcome_metrics |
| `scheduler_heartbeat` | Scheduler liveness (`last_heartbeat_at`) |
| `incidents` | Operational incidents (P0–P3) |
| `compliance_sla_alerts` | Queue SLA alert rows |
| `message_logs` | Email/SMS delivery telemetry |

---

## 5. Monitoring services

| Service | Schedule | Output |
|---|---|---|
| `sla_watchdog.py` | 10 min | Incidents + OPS email |
| `compliance_sla_monitor.py` | 5 min | Queue SLA alerts |
| `notification_failure_spike_monitor.py` | 5 min | OPS spike email |
| `risk_signal_regen_alert_monitor.py` | Staggered | P2 incidents |
| `delivery_reconciliation.py` | 15 min | Enriches job_runs delivery metrics |
| `build_health_summary_payload` | On demand | System Health + Control Centre input |

---

## 6. Admin dashboards

| UI | Route | API |
|---|---|---|
| System Health | `/admin/system-health` | `GET /api/admin/observability/health-summary` |
| Automation Control Centre | `/admin/automation` | job-runs, framework-audit, health-summary |
| Platform Status | `/admin/control-centre` | `GET /api/admin/control-centre/snapshot` |
| Incidents | `/admin/incidents` | `GET /api/admin/observability/incidents` |

---

## 7. Incident / alert producers

| Producer | Severity | Dedupe |
|---|---|---|
| SLA watchdog | P0–P2 | `incident_lifecycle_service` fingerprint |
| Startup reconciliation | P2 | fingerprint |
| Risk regen alert monitor | P2 | fingerprint + auto-resolve |
| Job success recovery | — | `incident_recovery.resolve_recovered_incidents_for_job` |
| Notification spike | email only | cooldown doc |
| Stripe webhook failures | admin alert | async |

---

## 8. Health scores (Platform Status)

Computed in `control_centre_service.py`:

- **Automation Health** — from overall_health + heartbeat + incidents
- **Job Confidence** — heuristic from critical job states
- **Security Risk** — from security dashboard summary
- **Revenue Health** — owner-only, billing signals

All derive from `build_health_summary_payload()` + security/revenue collectors — **single upstream truth for automation**.

---

## Authority chain

```
APScheduler → job_runner.run_instrumented → job_runs (+ queues)
                    ↓
         sla_watchdog / monitors → incidents
                    ↓
         build_health_summary_payload → System Health
                    ↓
         get_control_centre_snapshot → Platform Status
```
