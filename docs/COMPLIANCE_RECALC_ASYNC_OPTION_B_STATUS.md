# Compliance Recalculation — Option B (Async Queue) Implementation Status

**Purpose:** Avoid duplicating work. Current system uses **synchronous** recalc; Option B requires an **async queue + worker**. Below: what exists today vs what remains to implement.

---

## ALREADY IMPLEMENTED (sync path — do not duplicate)

| Item | Location | Notes |
|------|----------|--------|
| **Scoring formula** | `backend/services/compliance_scoring_service.py`: `calculate_property_compliance`, `recalculate_and_persist` | Deterministic; do not change. |
| **Property fields** | Property doc: `compliance_score`, `compliance_breakdown`, `compliance_last_calculated_at`, `compliance_version` | No `compliance_score_pending` yet. |
| **History snapshots** | `property_compliance_score_history` collection; written inside `recalculate_and_persist` | Exists. |
| **Audit** | `COMPLIANCE_SCORE_UPDATED` in `recalculate_and_persist` | Exists. No `COMPLIANCE_RECALC_FAILED` or `COMPLIANCE_SCORE_DRIFT_DETECTED` yet. |
| **Triggers (sync)** | All call `recalculate_and_persist` directly (blocking): | |
| | • Client upload: `routes/documents.py` (upload, bulk, zip) | |
| | • Client delete: `routes/documents.py` (client + admin delete) | |
| | • Verify/reject: `routes/documents.py` | |
| | • AI apply: `routes/documents.py` | |
| | • Property create: `routes/properties.py` | |
| | • Provisioning: `services/provisioning.py` | |
| | • Expiry rollover: `job_runner.run_expiry_rollover_recalc` | |
| **Admin observability** | `GET /api/admin/properties/{property_id}/compliance-score-history` | Returns current score + history. No queue-status endpoint. |
| **Tests** | `backend/tests/test_compliance_scoring_enterprise.py` | Determinism, recalculate_and_persist (history + audit), expiry job, dashboard reads stored. No queue/worker/idempotency/retry/drift tests. |

---

## NOT IMPLEMENTED (Option B — to add)

| # | Requirement | Status |
|---|-------------|--------|
| **1** | **Queue collection** `compliance_recalc_queue` with schema (property_id, client_id, trigger_reason, actor_type, actor_id, correlation_id, status, attempts, next_run_at, last_error, created_at, updated_at) and indexes (unique property_id+correlation_id, status+next_run_at, property_id+status) | **Missing** |
| **2** | **enqueue_compliance_recalc(property_id, client_id, trigger_reason, actor_type, actor_id, correlation_id)** — single central enqueue; idempotent by correlation_id; coalescing or single runnable job per property | **Missing** |
| **3** | **run_compliance_recalc_worker()** — fetch PENDING, mark RUNNING, call existing recalc, on success DONE, on error backoff + FAILED/DEAD, AuditLog COMPLIANCE_RECALC_FAILED | **Missing** |
| **4** | **Property field** `compliance_score_pending` (boolean): set true on enqueue, false when worker finishes. Frontend “Updating…” when pending | **Missing** (backend field + UI) |
| **5** | **Replace direct recalc with enqueue** in all trigger points (doc upload/delete/verify, admin upload/delete, AI apply, property create, provisioning, expiry job); use correlation_id per task spec | **Missing** (currently all call `recalculate_and_persist` directly) |
| **6** | **Drift detection** in worker: compare stored vs computed; if mismatch log `COMPLIANCE_SCORE_DRIFT_DETECTED`; then apply computed | **Missing** |
| **7** | **GET /api/admin/properties/{property_id}/compliance-recalc-status** — pending, last_calculated_at, last_queue_jobs | **Missing** |
| **8** | **Tests:** enqueue idempotency, upload enqueues + pending=true, worker processes → pending=false + score+history, failure retries → DEAD at ≥5, drift audit, admin triggers enqueue | **Missing** |

---

## Summary

- **Current behavior:** Synchronous. Every mutation calls `recalculate_and_persist` in the request (or in the expiry job). No queue, no worker, no `compliance_score_pending`, no retry/backoff, no drift logging.
- **To implement Option B:** Add queue collection + indexes, `enqueue_compliance_recalc`, worker job, `compliance_score_pending` (and optional UI badge), swap all trigger sites to enqueue instead of direct recalc, add drift check in worker, add compliance-recalc-status endpoint, add the required tests. Reuse existing `recalculate_and_persist` (or a thin wrapper) inside the worker — do not reimplement scoring.
