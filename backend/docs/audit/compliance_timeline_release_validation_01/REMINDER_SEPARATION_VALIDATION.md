# Reminder Separation Validation

**Programme:** COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01  
**Validated at:** 2026-06-02 (read-only code review + local tests)

## Verdict: **PASS (local design) — staging behaviour not re-verified**

Reminder scheduling must remain independent from Compliance Timeline customer-facing truth. Phase 2 changed **display** in reminder emails only; scheduling authority was not moved to the timeline projection.

---

## Scheduling authority (unchanged)

| Component | Role | Timeline coupling |
|---|---|---|
| `reminder_truth_service` | Reminder eligibility and windows | **None** — not modified in programme |
| `get_effective_expiry_date` in `jobs.py` | Reminder send scheduling anchor | **Independent** — still used for `due_date` calculation before send |
| `compliance_timeline.py` | Customer-facing projection | Exposes `reminder_start_date` / `reminder_window_days` as **informational** outputs only |

**Code reference (local working tree):** `jobs.py` schedules via `get_effective_expiry_date(current_req)`; customer email text uses `_reminder_customer_due_display()` which reads timeline label for presentation.

---

## Local test evidence

| Test | Assertion | Result |
|---|---|---|
| `test_reminder_start_date_separate_from_primary` | `reminder_start_date != primary_date` | **PASS** |
| `test_reminder_start_date_separate_from_primary` | `reminder_window_days == 30` when configured | **PASS** |

---

## Separation checklist

| Check | Status |
|---|---|
| Reminder windows unchanged by timeline calculator logic | **PASS** (calculator read-only; no reminder config writes) |
| Reminder cadence unchanged | **PASS** (no jobs.py cadence edits in programme scope) |
| Reminder configuration does not create renewal dates on requirement | **PASS** (no migration/repair scripts run) |
| Compliance Timeline does not replace scheduling anchor | **PASS** |
| Reminder services continue using authoritative expiry for scheduling | **PASS** — `get_effective_expiry_date` retained |
| Timeline label used only for customer display in reminder emails | **PASS** (Phase 2 `_reminder_customer_due_display`) |

---

## Staging gap

Reminder send behaviour on staging was **not** exercised (no authenticated send probe, no data mutation permitted). After programme deploy, re-validate:

1. Pick requirement with verified expiry and active reminder config
2. Confirm scheduled job uses effective expiry for window math
3. Confirm email body shows timeline label, not raw `due_date` heuristics
4. Confirm changing timeline presentation does not shift reminder schedule

---

## Risk note

If Phase 1/2 is deployed without committing, staging will continue using legacy reminder **and** legacy display — no erroneous timeline/scheduling coupling, but also **no Phase 2 display improvement**.
