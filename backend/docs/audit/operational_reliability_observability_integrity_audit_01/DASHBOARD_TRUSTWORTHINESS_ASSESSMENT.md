# Dashboard Trustworthiness Assessment

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

---

## Surface-by-surface assessment (staging, pre-remediation deploy)

| Surface | Trust level | Evidence |
|---|---|---|
| **Automation Control Centre** | **High** | Job runs API 200; direct `job_runs` ledger; manual run available |
| **System Health** | **Medium** | Data accurate but **55s load**; 3 jobs missing from state map |
| **Platform Status** | **Not trustworthy** | HTTP 500 — unavailable |
| **Incidents page** | **High** | API returns genuine open incidents; dedupe observed |
| **Alert emails** | **High** (design) | Fingerprint suppression; not tested end-to-end in this audit |
| **Recalc queue panel** | **High** | 0 pending/dead; matches queue semantics |

---

## Drift analysis

| Drift vector | Present? | Remediation |
|---|---|---|
| Scheduler vs health registry | **Yes** — 3 jobs | Registry fix |
| Health vs Control Centre | **Yes** — CC depends on health; both fail together on timeout | Batching fix |
| Incidents vs health count | **No** — both report 4 open | — |
| job_runs vs queue depth | **No** — queue empty, worker running | — |
| Frontend vs API | Not browser-tested; API is authority | — |

---

## False healthy dashboard conditions

| Condition | Found? |
|---|---|
| Hardcoded green status | No |
| Cache serving stale health | No — live Mongo reads |
| Missing jobs shown as OK | **Yes (pre-fix)** — invisible jobs |
| Empty result → green | No — `conditional_no_output` used |

---

## Post-remediation trust projection

| Surface | Expected trust |
|---|---|
| System Health | **High** — complete job map, sub-10s load |
| Platform Status | **High** — if 500 resolved by performance fix |
| Automation Control Centre | **High** — unchanged |
| Incidents | **High** — unchanged |

---

## Operator guidance

Until staging redeploy:

- Trust **Automation Control Centre job runs** and **Incidents** as authoritative
- Treat **Platform Status** as **down** — do not infer automation health from cached UI
- Use **System Health** with caution — allow full minute+ load; note 48 not 51 jobs

---

## Verdict

Dashboards are **architecturally single-source** but were **operationally untrustworthy on Platform Status** due to performance and registry gaps. Remediations target root causes without weakening governance.
