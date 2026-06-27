# Remaining Blockers — Audit 02

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-02

---

## P0 — Control Centre snapshot HTTP 500

Platform Status remains unavailable. Health summary is fixed; failure is in downstream collectors or an unhandled exception after health build.

**Action:** Render logs for `get_control_centre_snapshot`; bisect `_collect_revenue_block`, `get_security_dashboard_summary`, `summarize_workflow_drift_from_requirements_sample`, `list_work_order_job_class_mismatches`.

---

## P1 — Health summary latency (~18s)

Down from ~55s but above 15s validation target. Acceptable for staging validation; consider compound index `{job_name: 1, finished_at: -1, status: 1}` if latency regresses at production scale.

---

## P2 — Incident email lifecycle soak test

Code deployed; need ≥24h observation that unchanged DEGRADED P2 incidents do not re-email when suppression window expires.

---

## P2 — Open incidents (6) and delivery_unknown (20 rows)

Genuine operational conditions — not monitoring defects. Operator review required.

---

## P3 — Un-skip CI registry alignment tests

Prevent future registry drift (`test_automation_registry_alignment` in `conftest.py`).

---

## Closed since Audit 01

- Registry blind spot (48→51 jobs) — **closed**
- Health summary N+1 causing 55s latency / health 500 — **closed** (with `02e71254` hotfix)
- Batch aggregation regression on first deploy — **closed**
