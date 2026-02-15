# Compliance Score Lifecycle — Audit Findings

**Audit date:** 2026-02  
**Scope:** Enterprise compliance score lifecycle (scoring service, mutation triggers, persistence, history, audit, admin observability).

---

## 1) Current scoring logic

| Item | Location | Notes |
|------|----------|--------|
| **Scoring functions** | `backend/services/compliance_scoring_service.py`: `calculate_property_compliance(property_id, as_of_date)`, `recalculate_and_persist(property_id, reason, actor, context)` | Single source of truth; deterministic. |
| **Client-level API** | `backend/services/compliance_score.py`: `calculate_compliance_score(client_id)` | Reads stored property scores; lazy backfill only when a property has no stored score. |
| **Computed on GET?** | **NO** | GET `/api/client/compliance-score` returns stored property scores (aggregated). Recompute only for legacy backfill (once per property). |
| **Where score is stored** | **Property document** (`properties` collection): `compliance_score`, `compliance_breakdown`, `compliance_last_calculated_at`, `compliance_version` | Single atomic update per recalc. |
| **Score history** | **property_compliance_score_history** collection: `property_id`, `client_id`, `score`, `breakdown_summary`, `created_at`, `reason`, `actor` | Index: `(property_id, created_at desc)`. |
| **Trend / explanation** | `backend/services/compliance_trending.py`: `get_score_trend`, `get_score_change_explanation`; client-level history in `compliance_score_history` (date_key). | Trend uses client-level snapshots; property-level explanation reads stored breakdown when `property_id` is passed. |

---

## 2) Mutation triggers (recalculation)

| Trigger | Recalculates? | Where | Persistence / audit |
|---------|----------------|-------|----------------------|
| **A) Client uploads document (single)** | **YES** | `routes/documents.py` after upload: `recalculate_and_persist(property_id, REASON_DOCUMENT_UPLOADED, ...)` | Property fields + history + `COMPLIANCE_SCORE_UPDATED` |
| **B) Client ZIP / bulk upload** | **YES** | `routes/documents.py` after bulk loop and after zip loop: `recalculate_and_persist(property_id, REASON_DOCUMENT_UPLOADED, ...)` | Same |
| **C) Client deletes document** | **YES** | `routes/documents.py` after delete + revert: `recalculate_and_persist(property_id, REASON_DOCUMENT_DELETED, ...)` | Same |
| **D) Admin uploads document** | **YES** | `routes/documents.py` admin upload: `recalculate_and_persist(property_id, REASON_DOCUMENT_UPLOADED, ...)` | Same |
| **E) Admin deletes document** | **YES** | `routes/documents.py` admin delete: `recalculate_and_persist(property_id, REASON_DOCUMENT_DELETED, ...)` | Same |
| **F) AI apply-extraction** | **YES** | `routes/documents.py` apply-extraction: `recalculate_and_persist(property_id, REASON_AI_APPLIED, ...)` | Same |
| **G) Requirement status / mapping** | **YES** | Document verify/reject call `recalculate_and_persist(..., REASON_REQUIREMENT_CHANGED)`. Provisioning calls `recalculate_and_persist(..., REASON_REQUIREMENT_CHANGED)` per property. | Same |
| **H) Property create** | **YES** | `routes/properties.py` after requirements + `_update_property_compliance`: `recalculate_and_persist(property_id, REASON_PROPERTY_CREATED, ...)` | Same |
| **H) Property delete** | **N/A** | No recalc (optional no-op per spec). | — |
| **I) Date rollover (expiry)** | **YES** | `job_runner.run_expiry_rollover_recalc()` (scheduled daily): finds properties with requirements in expiry window, calls `recalculate_and_persist(property_id, REASON_EXPIRY_ROLLOVER, system_actor, ...)` | Same |

---

## 3) Observability

| Item | Exists? | Details |
|------|---------|---------|
| **Score history snapshots** | **YES** | `property_compliance_score_history`: per-recalc snapshot with reason and actor. |
| **last_calculated_at and version** | **YES** | Property: `compliance_last_calculated_at`, `compliance_version` (rules version). |
| **Audit log score deltas** | **YES** | `COMPLIANCE_SCORE_UPDATED`: `previous_score`, `new_score`, `reason`, `delta`, `actor_role` in metadata. |
| **Admin: property score + breakdown** | **YES** | Client full-status returns full property docs (include stored score fields). Audit logs filterable by `action=COMPLIANCE_SCORE_UPDATED`. |
| **Admin: score history timeline (property)** | **YES** | GET `/api/admin/properties/{property_id}/compliance-score-history` returns last N snapshots (read-only). |

---

## 4) Summary

- **Score is mutation-driven:** Recalculation runs on document upload/delete (client + admin), verify/reject, bulk/zip upload, AI apply-extraction, property create, provisioning, and daily expiry rollover. Not on GET (except lazy backfill for legacy properties).
- **Where score is stored:** Property: `compliance_score`, `compliance_breakdown`, `compliance_last_calculated_at`, `compliance_version`. History: `property_compliance_score_history`.
- **Missing triggers:** None; all listed mutations trigger recalc.
- **Enterprise observability:** History, version, and audit deltas are in place. Admin can view score/breakdown via client full-status and audit logs; admin property score-history endpoint added for timeline view.
