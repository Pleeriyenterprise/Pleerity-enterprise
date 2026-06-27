# Health Score Validation

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

---

## Score sources

| Score | Computed in | Inputs |
|---|---|---|
| **Automation Health** | `_compute_automation_health_score(health)` | `overall_health`, heartbeat stale, open P0/P1, summary counts |
| **Job Confidence** | Heuristic in `get_control_centre_snapshot` | Critical job states (healthy_like vs failed/degraded/missed) |
| **Security Risk** | `_compute_security_risk_score(sec_full)` | Security dashboard 7d summary |
| **Revenue Health** | `_compute_revenue_health_score(rev)` | Owner-only billing block |
| **Platform Status label** | `_control_status(...)` | Combines automation, security, revenue, heartbeat, P0/P1 |

All automation scores **derive from `build_health_summary_payload()`** — single upstream truth.

---

## Staging validation (pre-remediation)

| Score | Observed | Consistent with runtime? |
|---|---|---|
| Automation Health | Not retrieved — Control Centre 500 | **No** — surface unavailable |
| Job Confidence | Not retrieved | **No** |
| `overall_health` (upstream) | `degraded` | **Yes** — 1 missed, 1 degraded job, 20 delivery_unknown stale, 4 incidents |
| Heartbeat | Not stale | **Yes** — scheduler alive |
| Recalc queue | 0 pending/dead | **Yes** — queue healthy |

---

## False-healthy score analysis

| Scenario | Can score show healthy incorrectly? | Verdict |
|---|---|---|
| Worker dead, heartbeat stale | No — heartbeat gates overall_health | Safe |
| Job never in registry | **Yes (pre-fix)** — job invisible, scores ignore it | **Fixed** |
| Zero work conditional run | No — `conditional_no_output`, not counted as healthy critical path | Safe |
| Open P0/P1 | Forces incident status badge | Safe |
| Slow health build timeout | Dashboard error, not fake healthy | Safe (500, not 200 healthy) |

---

## Weighting review

Job Confidence applies penalties: failed ×8, degraded ×4, missed ×6. Heuristic flagged `heuristic: true` in API — operators directed to Automation Centre for detail. **Appropriate disclaimer.**

---

## Post-remediation expectation

After deploy:

- Automation Health should reflect all 51 jobs
- Job Confidence denominator uses complete critical job set
- Scores refresh within seconds of health batching fix

---

## Verdict

**Health scoring logic is sound** but was **fed incomplete inputs** (48/51 jobs) and **unavailable on Platform Status** due to performance failure. Remediations address input completeness and availability.
