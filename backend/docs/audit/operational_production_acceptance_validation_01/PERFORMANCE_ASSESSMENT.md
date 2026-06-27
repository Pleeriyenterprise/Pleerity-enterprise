# Performance Assessment

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Environment:** Staging  
**SHA:** `f2c10442`

---

## Measured latencies (authenticated admin)

| Surface | Latency | Target | Pass |
|---|---|---|---|
| System Health (`/health-summary`) | **16.4s** | <30s | Yes |
| Platform Status (`/control-centre/snapshot`) | **30.6s** | <60s | Yes |
| Incidents list | **1.5s** | <10s | Yes |
| Job runs (limit 10) | **2.4s** | <10s | Yes |

**Evidence:** `RUNTIME_ACCEPTANCE.json` → `phase_9_performance`

---

## Analysis

| Factor | Impact |
|---|---|
| Health summary 4× `$top` aggregations on `job_runs` | Primary cost (~16s) — 72% improvement vs pre-Audit-01 N+1 (~55s) |
| Control Centre chains health + security + engagement + workflow drift | +~14s over health alone |
| Engagement property scan (up to 50k docs) | Minor on staging (~0.4s local) |
| Workflow drift sample (120 requirements enrich) | ~3s |

---

## Scalability notes

- No gateway timeout observed at current staging volume (all responses <60s).
- Compound index `{job_name: 1, finished_at: -1, status: 1}` recommended before production scale if latency regresses.
- Control Centre should not be polled sub-30s; UI poll interval should remain ≥60s.

---

## Database load

Batch aggregations replace 204 sequential point queries — material reduction in query count. No evidence of runaway aggregation memory after `$top` hotfix (`02e71254`).
