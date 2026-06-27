# Infrastructure Behaviour Assessment

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01  
**Host:** Render (staging `pleerity-enterprise.onrender.com`)

---

## Observed infrastructure events

| Event | Evidence | Duration |
|---|---|---|
| Container recycle / deploy | Version SHA change; connection resets during deploy polling; job_run gaps | ~7–14 min |
| Cold start | API `/version` unavailable briefly; readiness `post_db_initialization` | ~1–3 min |
| Application boot | Scheduler registers after DB ready | Observed in local bisect logs |

---

## Not observed

| Factor | Evidence |
|---|---|
| Memory pressure / OOM | No failed jobs with OOM errors; heartbeat resumes cleanly |
| CPU throttling | No elongated job durations outside deploy windows |
| Mongo outage | DB queries succeed throughout; health summary 200 |
| Network partition | API reachable; no sustained 5xx outside deploy |
| Provider outage (Postmark/SMS) | Unrelated to alert cluster under investigation |

---

## Render restart behaviour

```
Deploy triggered (git push → develop)
    ↓
Existing container SIGTERM (~0–30s)
    ↓
New container boot + pip/start (~2–5 min)
    ↓
DB connect + heavy_startup + scheduler register (~1–3 min)
    ↓
First heartbeat + high-freq jobs (~2 min)
    ↓
Full operational (~7–14 min from deploy start)
```

**Automatic recovery:** Yes — all deploy-cluster incidents auto-resolved.  
**Customer compliance integrity:** Protected — recalc queue 0 pending; no score corruption during gaps.

---

## Severity appropriateness

| Alert | Severity during deploy | Appropriate? |
|---|---|---|
| Heartbeat stale | P1 | Yes — genuine liveness loss |
| risk_signal_regen missed | P0 | Arguably high for deploy — but max_delay=3min is intentional for near-real-time job |
| scheduled_admin_communications | P0 | Same |

**Optional improvement:** Set `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` in deploy hook to suppress P2 transient SLA alerts (existing mechanism — not suppression of monitoring).

---

## Verdict

Remaining deploy-cluster alerts are **infrastructure behaviour**, not application bugs. Recovery is **automatic**. Customer-facing data **remained correct** during interruptions.
