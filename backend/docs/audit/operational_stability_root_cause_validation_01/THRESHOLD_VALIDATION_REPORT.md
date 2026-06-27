# Threshold Validation Report

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

**Principle:** Do not increase timeouts to silence warnings. Validate whether thresholds detect genuine unhealthy behaviour.

---

## Heartbeat

| Setting | Value | Verdict |
|---|---|---|
| Job interval | 2 min | OK |
| Stale threshold | 5 min (300s) | **Correct** — 2 missed beats + margin |
| Deploy gap | 414–435s | Correctly triggers — **not false positive** |
| Recommendation | Keep 300s; use deploy suppression for planned deploys | |

---

## High-frequency jobs (P0 SLA)

| Job | Interval | max_delay_minutes | Severity | Deploy triggers alert? |
|---|---|---|---|---|
| risk_signal_regen_worker | 30s | **3** | P0 | Yes (~4–5 min gap) |
| scheduled_admin_communications | 2 min | **5** | P0 | Yes (~6 min gap) |
| notification_retry_worker | 1 min | **5** | P0 | Would trigger if gap >5 min — **did not occur** |

**Assessment:** Thresholds are **aggressive by design** for near-real-time automation. They **correctly detect** deploy outages. They ** routinely exceed during Render restarts** (~7–14 min).

| Option | Recommendation |
|---|---|
| Increase max_delay globally | **Reject** — would miss real outages |
| Deploy suppression window | **Accept** — existing `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` |
| P0 → P1 during deploy only | **Consider** — product decision, not required for GO |

---

## Daily / hourly jobs

| Job | max_delay | Incident in window | Verdict |
|---|---|---|---|
| compliance_check_evening | 1560 min (26h) | Open — job **failed** not delayed | Threshold **correct** |
| work_order_schedule_reminders | 90 min | Resolved after deploy | Threshold **correct** |

---

## SLA watchdog grace

| Setting | Value | Verdict |
|---|---|---|
| GRACE_PERIOD_NEXT_RUN_FUTURE_SEC | 60s | OK for startup |
| Success/degraded only for SLA | Failed runs don't count | **Correct** — explains open evening compliance incident despite 18:00 run |

---

## Verdict

Thresholds are **meaningful and not misconfigured**. Deploy-induced alerts are **expected transient behaviour**, not threshold bugs. No threshold changes recommended except optional deploy-window suppression for P0 transients.
