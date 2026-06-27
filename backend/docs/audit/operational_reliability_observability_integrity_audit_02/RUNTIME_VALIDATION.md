# Runtime Validation — Audit 02

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-02  
**Validated at:** 2026-06-27T15:44:42Z  
**Environment:** Staging (`https://pleerity-enterprise.onrender.com`)  
**Deployed SHA:** `02e7125443e020296ea8ac9a7cf23374fcd877f8`

---

## Summary

| Check | Pre-remediation (Audit 01) | Post-remediation (Audit 02) |
|---|---|---|
| Deploy SHA | `2d64104e` | `02e71254` |
| Health summary HTTP | 200 | **200** |
| Health summary latency | ~55s | **~18s** (72% reduction) |
| Jobs in health summary | 48/51 | **51/51** |
| Control Centre HTTP | 500 | **500** (unchanged) |
| Scheduler registered | 51 | **51** (after warmup) |
| Recalc queue | Healthy | **Healthy** |
| `delivery_unknown_stale` | 20 | **20** |
| Open incidents | 4 | **6** (deploy transient P0/P1 added) |

---

## Audit 01 remediation validation

| Remediation | Result |
|---|---|
| Registry 51/51 | **Pass** — all scheduled jobs visible in health summary |
| Health summary batch fetch | **Pass (partial latency)** — HTTP 200; ~18s vs ~55s pre-fix; target was <15s |
| Outcome family map | **Pass (code)** — deployed with `12ea3502`; governance tests green locally |
| Incident email lifecycle | **Deployed** — code live; soak period required to prove no hourly re-email |
| Platform Status / Control Centre | **Fail** — snapshot still HTTP 500 after ~28s |

---

## Hotfix note (`02e71254`)

Initial batch aggregation (`12ea3502`) used collection-wide `$sort` before `$group`, causing health summary **HTTP 500** on staging `job_runs` scale. Replaced with per-job `$top` grouped aggregation + `finished_at` filter. Health summary restored.

---

## Evidence

Machine-readable: `RUNTIME_VALIDATION.json`  
Script: `backend/tmp_operational_reliability_staging_audit_02.py`
