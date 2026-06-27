# Chaos Testing Results

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Environment:** Staging only

---

## Scope note

Full controlled chaos (manual Render restart, network partition, queue injection) was not executed as destructive infra operations in this session. **Observed chaos from deploy restarts** provides partial evidence.

---

## Observed: application restart (deploy `f2c10442`)

| Expected behaviour | Observed | Pass |
|---|---|---|
| Heartbeat stale incident | P1 opened during restart window | Yes |
| Transient P0 SLA misses | scheduled_admin_communications, risk_signal_regen_worker (recovered) | Yes |
| Health summary recovery | HTTP 200 after warmup, 51 jobs | Yes |
| Control Centre recovery | HTTP 200 post-fix | Yes |
| Queue convergence | recalc pending=0 throughout | Yes |
| Customer compliance corruption | Not observed | Yes |

---

## Not executed (requires explicit infra authorization)

| Scenario | Status |
|---|---|
| Manual Render service restart mid-job | Not run |
| Database reconnect simulation | Not run |
| Artificial queue backlog injection | Not run |
| Notification provider delay injection | Not run |
| Worker timeout / retry exhaustion | Not run |
| Duplicate execution test | Not run |

---

## Interim verdict

Deploy-restart behaviour demonstrates **incident creation, dashboard update, and automatic recovery** for scheduler heartbeat and SLA watchdog paths. Full chaos matrix **not complete** — condition for unconditional GO.

---

## Recommended follow-up (staging)

1. Trigger Render manual restart during low-traffic window; verify heartbeat incident → recovery → closure.
2. Pause `compliance_recalc_worker` briefly; verify queue depth rises then converges after resume.
