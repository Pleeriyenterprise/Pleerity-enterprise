# MongoDB Platform Observability — Validation

**Audit ID:** `MONGODB-STORAGE-PREVENTION-VALIDATION-01` / Phases 7–9 (+ readiness)  
**Date:** 2026-08-06

---

## Critical finding

| Signal | Value |
|--------|-------|
| `GET /api/health` | `status: healthy`, readiness `ready` |
| `scheduler_heartbeat.last_heartbeat_at` | `2026-07-16T17:39:33Z` (unchanged over 130s) |

**Dashboards/API health must not report healthy while the scheduler has been dead for weeks.** This is a production-readiness defect independent of storage remediation deploy.

---

## Surfaces vs remediations

| Surface | Expected remediation signal | Live status |
|---------|----------------------------|-------------|
| System Health / health-summary | `mongo_storage` block | **Not on deployed build** |
| Platform Status / Control Centre | storage alert card | **Not on deployed build** |
| Automation Control Centre | job states + storage alert | Scheduler inactive; storage field absent |
| Incident engine | capacity incidents ≥85% | Code untracked |
| Telemetry pipeline (job_runs / OEP) | idle-skip + retention | Untracked; scheduler quiet |
| Queue / worker health | via existing health-summary | Stale without fresh job_runs |

---

## Growth / soak (Phase 7)

Cannot certify stabilised growth: no scheduler ticks. After deploy + heartbeat recovery, require ≥30–60 minutes soak with:

- idle high-freq jobs → ~0 new `job_runs` / OEP
- non-idle work → rows created
- cluster % stable or slowly changing

---

## Governance (Phase 8) — PASS

- Cleanup utility refuses `pleerity_production`
- Production counts intact in sample
- Logical DB isolation preserved
- Physical shared Flex cluster remains a risk

---

## Long-term readiness (Phase 10)

| Question | Evidence-based answer |
|----------|----------------------|
| Retention policies sufficient? | Sufficient **when enabled** after deploy; dry-run shows aged reminder logs eligible |
| Storage budgets appropriate? | 46.8% OK short-term; shared Flex still couples envs |
| Alerts early enough? | 60% warning in code — **unproven live** |
| Separate staging/prod clusters? | **Still recommended** |
| Atlas Flex suitable pre-launch? | **Only after** deploy + soak + separation plan; not as shared long-term SoR for both envs |
| M10 before customer growth? | **Yes** — plan before material customer write volume on production |

**Launch readiness:** `NOT_READY_PENDING_DEPLOY_AND_SOAK`
