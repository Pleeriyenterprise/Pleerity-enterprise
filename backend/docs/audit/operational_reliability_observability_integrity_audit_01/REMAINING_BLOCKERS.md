# Remaining Blockers (Manual Intervention)

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

---

## P0 — Deploy remediations to staging

Code fixes are **local only**. Staging still runs pre-audit code (48-job health summary, N+1 queries, Platform Status 500).

**Action:** Deploy `develop` (or audit branch) to staging Render service and re-run runtime verification.

---

## P1 — Platform Status 500 confirmation

After health batching deploy, if snapshot still returns 500:

1. Capture Render application logs for `get_control_centre_snapshot` stack trace
2. Isolate failing sub-collector (revenue, workflow drift, work-order mismatches)
3. Add targeted error boundary with structured log (not silent fallback)

---

## P2 — Open operational incidents on staging

4 open P2 incidents including `activation_reminder_processing` missed SLA.

**Action:** Operator review — confirm job ran since incident, acknowledge or resolve via incident lifecycle; verify recovery notification if applicable.

---

## P2 — Delivery unknown stale rows (20)

20 job runs with `delivery_unknown > 0` older than reconciliation window.

**Action:** Run `delivery_reconciliation` manually or verify Postmark/message_logs linkage; not a compliance score authority issue but affects health degraded state.

---

## P3 — Un-skip CI registry alignment tests

`test_automation_registry_alignment` skipped in `conftest.py` — re-enable to prevent future registry drift.

---

## P3 — Production validation deferred

This audit scoped to **staging only** per mission constraints. Production operational surfaces not probed.

---

## Not blockers

- Compliance timeline programme — separate release track
- Enrich performance (~5.8s) — monitoring item, not automation failure
