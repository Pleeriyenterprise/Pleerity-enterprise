# Heartbeat Runtime Analysis

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01

---

## Mechanism

```python
# job_runner.run_scheduler_heartbeat — every 2 min
await db.scheduler_heartbeat.update_one(
    {"_id": "default"},
    {"$set": {"last_heartbeat_at": now.isoformat(), ...}},
    upsert=True,
)
```

**Staleness threshold:** `HEARTBEAT_STALE_SECONDS = 300` (5 minutes)  
**Watchdog:** `sla_watchdog` checks collection every 10 min; creates P1 if stale

---

## Current state (end of validation)

```json
{
  "last_heartbeat_at": "2026-06-27T22:31:43.322091+00:00",
  "updated_at": "2026-06-27T22:31:43.322091+00:00"
}
```

---

## Stale episodes

| Episode | Last HB before gap | Gap duration | Stale threshold exceeded? | Incident |
|---|---|---|---|---|
| Deploy A | 15:37:34 | 435.6s | Yes (+135s) | P1, resolved |
| Deploy B | 21:48:49 | 414.0s | Yes (+114s) | P1, resolved |

---

## Heartbeat job runs vs collection

249 successful `scheduler_heartbeat` job_runs in window — collection timestamp aligns with last successful run. **No persistence-only delay observed.**

---

## False positive assessment

| Scenario | False positive? |
|---|---|
| Deploy restart | **No** — scheduler genuinely down |
| Steady state | **No** — 249/249 successes, no stale episodes outside deploys |

---

## Threshold validation

| Parameter | Value | Assessment |
|---|---|---|
| Heartbeat interval | 2 min | Appropriate |
| Stale threshold | 5 min | **Correct** — allows 2 missed beats + buffer; deploy gaps (~7 min) correctly trigger |
| P1 severity | P1 | Appropriate for scheduler liveness |

**Do not increase threshold** — would miss real scheduler death. Use deploy suppression for planned maintenance instead.

---

## Verdict

Heartbeat monitoring is **accurate**. Stale alerts during deploys are **correct operational protection**, not monitoring defects.
