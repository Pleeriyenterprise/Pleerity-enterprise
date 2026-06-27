# Remediation Validation — Audit 02

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-02  
**Staging SHA:** `02e7125443e020296ea8ac9a7cf23374fcd877f8`

---

## 1. Job schedule registry (51/51)

**Status:** Validated on staging  
**Evidence:** `jobs_count: 51`, `scheduler_runtime.registered_jobs_count: 51`  
**New jobs now tracked:** `commercial_entitlement_expiry`, `scheduled_admin_communications`, `work_order_schedule_reminders`

---

## 2. Health summary batch fetch

**Status:** Validated with hotfix  
**Commits:** `12ea3502` (initial batch), `02e71254` (`$top` hotfix)  
**Evidence:** HTTP 200, 51 job states, latency ~17–18s (was ~55s)  
**Regression:** `12ea3502` alone returned HTTP 500 — global `$sort` exceeded staging aggregation limits  
**Residual:** Latency still above 15s aspirational target; acceptable for staging but monitor on production scale

---

## 3. Outcome family map

**Status:** Code validated locally (7 tests pass)  
**Runtime:** Not independently re-probed; Control Centre 500 blocks Platform Status outcome-family UI

---

## 4. Incident email lifecycle

**Status:** Deployed; runtime proof incomplete  
**Code change:** Removed periodic re-email when suppression window expires for unchanged DEGRADED incidents  
**Staging observation:** Legacy incidents retain prior `last_alert_email_at` timestamps (expected). No new re-emails observed during validation window. **Soak test ≥24h recommended** to confirm P2 incidents do not re-email hourly.

---

## 5. SLA watchdog heartbeat path

**Status:** Deployed  
**Change:** Heartbeat stale alerts route through `_detect_and_alert` dedupe lifecycle  
**Staging:** Transient P1 "Scheduler heartbeat stale" opened during deploy restart (expected)

---

## Local test evidence

```
18 passed — incident_lifecycle, sla_watchdog, outcome family governance
```
