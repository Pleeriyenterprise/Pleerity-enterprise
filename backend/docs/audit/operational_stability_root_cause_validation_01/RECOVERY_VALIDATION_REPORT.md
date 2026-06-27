# Recovery Validation Report

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

---

## Deploy-cluster incidents (all resolved)

| Incident | Created | Recovered | Resolved | Recovery mechanism |
|---|---|---|---|---|
| Heartbeat stale (A) | 15:23 | 15:50 | 16:10 | `check_and_resolve_heartbeat_incidents` |
| risk_signal_regen P0 (A) | 15:24 | 15:29 | 15:44 | Job success → auto resolve |
| admin comms P0 (A) | 15:24 | 15:30 | 15:46 | Job success → auto resolve |
| work_order reminders P2 | 16:00 | 17:20 | 18:20 | Job success → auto resolve |
| Heartbeat stale (B) | 21:54 | 22:10 | 22:30 | Heartbeat fresh → auto resolve |
| risk_signal_regen P0 (B) | 21:54 | 21:59 | 22:15 | Job success → auto resolve |

---

## Recovery checklist (deploy clusters)

| Step | Verified |
|---|---|
| Heartbeat resumes | ✓ — 22:31:43 fresh |
| Jobs resume | ✓ — continuous job_runs post-recovery |
| Queues drain | ✓ — pending=0 at recovery metadata |
| Workers recover | ✓ — compliance_recalc, risk_regen, notification_retry all succeeding |
| Incidents update lifecycle | ✓ — OPEN → RECOVERED → RESOLVED |
| Recovery notification | Partial — auto-resolve notes in metadata; email on recovery per lifecycle design |
| Incidents close | ✓ — all deploy-cluster incidents resolved |
| Health restored | Partial — `attention_required` due to **other** open P2 (evening compliance, daily_reminders degraded, delivery_unknown) |

---

## Open incident — compliance_check_evening

| Step | Status |
|---|---|
| Root cause fixed (`f2c10442`) | ✓ |
| Next scheduled run | 2026-06-28T18:00 UTC |
| Incident closure | **Pending** next success |
| Manual resolve option | Available if ops confirms fix without waiting |

**No open deploy-cluster incidents remain.**

---

## Verdict

Recovery automation **works as designed**. No incident should remain open after complete recovery **except** compliance_check_evening which awaits next successful scheduled run after code fix.
