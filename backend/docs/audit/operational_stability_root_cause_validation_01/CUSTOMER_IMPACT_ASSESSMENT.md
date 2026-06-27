# Customer Impact Assessment

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

---

## Deploy-cluster alerts (Clusters A & C)

| Customer surface | Impact during ~7–14 min outage |
|---|---|
| Compliance scores | **Not incorrect** — recalc queue idle; no partial writes |
| Portfolio scores | **Not incorrect** |
| Risk signals | **Delayed refresh** — regen resumed; queue empty |
| Reminders | **Delayed** — daily_reminders runs on separate schedule |
| Reports | **Delayed** if hourly slot missed |
| Notifications | **Retry worker paused** — no sends lost (503/503 success in window) |
| Work orders | **Reminder delayed** ~1h during deploy cluster C |
| Dashboards | **Stale up to gap duration** — not wrong |
| Admin comms | **Delayed ~6 min** |

**Classification:** Operational delay only — **zero customer data corruption**.

---

## compliance_check_evening failure (Cluster B)

| Surface | Impact |
|---|---|
| Evening compliance batch check | **Did not complete successfully** on 2026-06-27 |
| Compliance scores | **Stale** (prior day's batch state) — **not fabricated incorrect scores** |
| Customer-visible alerts | Depends on batch output — check did not publish new results |
| Risk / reminders / reports | **Unaffected** |

**Classification:** **Stale operational output** — one missed batch cycle. Fix deployed before next run.

---

## notification_retry_worker

**No alert in window. No customer impact.**

---

## Integrity guards confirmed

- Failed jobs recorded as `failed` in `job_runs` — not hidden
- Health summary reports degraded/attention_required — not false healthy
- Queue metrics show pending work if backlog exists — 0 throughout

---

## Verdict

Remaining alerts represent **operational protection** with **minimal customer impact**. No evidence of incorrect compliance data. Worst case: **delayed or stale** outputs, clearly signalled to administrators.
