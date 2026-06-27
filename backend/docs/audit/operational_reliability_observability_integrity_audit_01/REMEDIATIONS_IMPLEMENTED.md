# Remediations Implemented

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01  
**Status:** Local — **requires staging deploy to activate**

---

## 1. Job schedule registry completeness

**File:** `backend/services/job_schedule_registry.py`

Added SLA/health metadata for:

| Job | Critical | Max delay | Frequency |
|---|---|---|---|
| `commercial_entitlement_expiry` | No | 26h | Daily |
| `scheduled_admin_communications` | No | 5 min | Every 2 min |
| `work_order_schedule_reminders` | No | 90 min | Hourly |

**Result:** 51/51 scheduled jobs now in health summary and SLA watchdog scope.

---

## 2. Control Centre outcome family map

**File:** `backend/services/control_centre_outcome_aggregation.py`

- Added `commercial_entitlement_expiry` → `billing_and_subscription_jobs`
- Added `rent_operations_daily_job` → `notification_and_delivery`
- Sorted all 51 keys alphabetically (CI governance test)

**Result:** Platform Status 24h outcome families align with job inventory.

---

## 3. Health summary query batching

**File:** `backend/routes/observability.py`

- New `_fetch_jobs_detail_for_health_summary()` — 4 Mongo aggregations replace 4×N point queries
- Preserves identical `jobs_detail` / `job_states` output shape

**Expected result:** Health summary latency reduction from ~55s to low seconds on staging.

---

## 4. Tests verified

```
tests/test_automation_registry_alignment.py — registry 51/51 (when un-skipped)
tests/test_control_centre_outcome_family_governance.py — 7 passed
```

---

## Not changed (by design)

- No monitoring suppression
- No hardcoded healthy overrides
- No feature flag changes
- No production deployment
- No queue bypass or retry weakening
