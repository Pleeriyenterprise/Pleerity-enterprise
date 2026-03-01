# Score Ledger + Audit Trail – Task vs Codebase Audit

**Task:** Implement an enterprise-grade “Score Ledger + Audit Trail” that records every score change with before/after, triggers, timestamps, driver breakdown, and export.  
**Scope:** Statement-of-account style history for compliance score; viewable in client dashboard; CSV (and later PDF) export; RBAC.

**This audit lists what exists, what is missing, and the safest way to implement without duplicating or conflicting with current behaviour. No code changes are made here.**

---

## 1. Current implementation (no duplication)

### 1.1 Collections and write paths

| Item | Purpose | Written from | Schema (key fields) |
|------|---------|--------------|---------------------|
| **score_change_log** | Per-property score change log | `recalculate_and_persist` only | `property_id`, `client_id`, `previous_score`, `new_score`, `delta`, `reason`, `changed_requirements[]`, `created_at`, `actor` |
| **property_compliance_score_history** | Per-recalc snapshot (after only) | `recalculate_and_persist` only | `property_id`, `client_id`, `score`, `breakdown_summary` (status_score, expiry_score, document_score, overdue_penalty_score, risk_score), `created_at`, `reason`, `actor` |
| **score_events** | Client-level “What Changed” + trend | Routes (document upload/apply, property add/update) + job_runner after recalc | `client_id`, `event_type`, `score_before`, `score_after`, `delta`, `property_id`, `requirement_id`, `document_id`, `actor_*`, `metadata`, `created_at` |
| **audit_logs** | General audit (admin + client timeline) | Many routes + recalc worker (COMPLIANCE_SCORE_UPDATED, COMPLIANCE_SCORE_DRIFT_DETECTED) | `action`, `client_id`, `resource_type`, `resource_id`, `before_state`, `after_state`, `metadata`, `timestamp` |

- **Single write path for score persistence:** All score changes go through **enqueue_compliance_recalc** (per property). The **compliance_recalc_worker** runs **recalculate_and_persist(property_id, trigger_reason, actor, context)**. So `recalculate_and_persist` is the only place that updates property score, writes **score_change_log** and **property_compliance_score_history**, and creates **COMPLIANCE_SCORE_UPDATED** audit.  
- **score_events** is written in two places: (1) in routes for “what happened” (DOCUMENT_UPLOADED, DOCUMENT_CONFIRMED, etc.) without score deltas at that moment; (2) in the worker after recalc as **SCORE_RECALCULATED** with client-level `score_before`/`score_after`/`delta` (portfolio score, not property).

### 1.2 Trigger reasons (current)

Defined in `compliance_recalc_queue.py` and passed to `recalculate_and_persist` as `reason`:

- TRIGGER_DOC_UPLOADED, TRIGGER_DOC_DELETED, TRIGGER_DOC_STATUS_CHANGED  
- TRIGGER_AI_APPLIED, TRIGGER_ADMIN_UPLOAD, TRIGGER_ADMIN_DELETE  
- TRIGGER_EXPIRY_JOB, TRIGGER_PROVISIONING  
- TRIGGER_PROPERTY_CREATED, TRIGGER_PROPERTY_UPDATED, TRIGGER_LAZY_BACKFILL  

Queue job payload: `property_id`, `client_id`, `trigger_reason`, `actor_type`, `actor_id`, `correlation_id`. **No requirement_id or document_id** in the queue today.

### 1.3 What recalculate_and_persist has access to

- **Before:** `previous_score`, `previous_breakdown` (legacy keys: status_score, expiry_score, document_score, overdue_penalty_score, risk_score), `previous_score_breakdown` (per-requirement).  
- **After:** `result` from `calculate_property_compliance` → `score`, `grade`, `breakdown`, `score_breakdown`, `weights_version`.  
- **Context:** `reason`, `actor`, `context` (from worker: correlation_id, trigger_reason). So **driver deltas** (status, expiry/timeline, documents, overdue_penalty) can be computed inside `recalculate_and_persist` from previous_breakdown vs new breakdown. **rule_version** can be set from `result.get("weights_version", WEIGHTS_VERSION)`.

### 1.4 APIs and UI today

- **Client**
  - **GET /api/client/score/changes** – “What Changed” list from **score_events** (title, details, delta, deep links).  
  - **GET /api/portfolio/audit-timeline** – General audit timeline (client-scoped actions from **audit_logs**).  
  - **ClientAuditLogPage** (`/audit-log`) – Uses audit-timeline; no score-specific ledger.  
  - **ReportsPage** (`/reports`) – Report generation/download; no “Score History” or ledger table.  
- **Portfolio**
  - **GET /api/portfolio/properties/{id}/compliance-detail** – Can include `score_delta`, `score_change_summary` from **score_change_log** (latest entry).  
  - **GET /api/portfolio/properties/{id}/score-history** – Returns last N entries from **score_change_log** (property_id, client_id scoped).  
- **Admin**
  - **GET /api/admin/audit-logs** – Filter by client_id, action, date; no ledger-specific endpoint.  
  - **GET /api/admin/properties/{id}/compliance-score-history** – **property_compliance_score_history** snapshots.  

There is **no** dedicated **GET /api/ledger** or **score_ledger_events** collection. There is **no** client UI that shows a “Score History” table with before/after/delta and driver breakdown. There is **no** CSV export for score changes.

---

## 2. Task requirements vs current state

| Requirement | Task | Current | Gap / conflict |
|-------------|------|---------|----------------|
| **Data model** | New collection **score_ledger_events** with before/after, delta, trigger_type, trigger_label, refs (property_id, requirement_id, document_id), before/after_grade, drivers_before/after/delta, rule_version, evidence, created_at. | **score_change_log**: property-scoped, before/after/delta/reason/actor; no drivers, no grades, no rule_version, no requirement_id/document_id. **score_events**: client-level, event_type, score_before/after, delta, refs; no drivers, no grades. | Task asks for a **richer, immutable ledger** with drivers and rule_version. Existing tables are partial overlap; neither is a full “statement-of-account” ledger. |
| **Indexes** | client_id + created_at desc; client_id + property_id + created_at desc; client_id + trigger_type + created_at desc. | score_change_log has no dedicated indexes in database.py. score_events has (client_id, created_at) and (client_id, event_type, created_at). | Ledger would need its own collection and indexes. |
| **Ledger write helper** | Single **log_score_change({...})** used by ALL score-impacting actions; inputs include refs, before/after, drivers_before/after, rule_version, evidence; compute delta + drivers_delta and insert. | No shared helper. **recalculate_and_persist** writes score_change_log (and history + audit) with delta and changed_requirements; it has before/after scores and breakdowns but does not write drivers_before/after/delta or rule_version to a ledger. | Need a **single write point** for the new ledger (prefer inside **recalculate_and_persist** so every recalc produces one ledger entry; no double-logging). |
| **Hook into existing flows** | Before change → read score/drivers; apply change; recompute; call log_score_change. Idempotency (e.g. event_hash or request_id). | Recalc is **async** (enqueue → worker). Worker has no “before” read in the same process as the user action; “before” is read at worker run time (current property state). So “before” is already correct when worker runs. Idempotency today: queue dedup by (property_id, correlation_id). | **No conflict.** Ledger write should happen **inside recalculate_and_persist** once per run; correlation_id can be stored on the ledger entry and used to avoid duplicate inserts if the same job is retried (optional idempotency key). |
| **API** | GET /api/ledger?client_id=...&property_id=...&trigger_type=...&from=...&to=...&limit=50&cursor=... (paginated, newest first). GET /api/ledger/export.csv (same filters, stream CSV). PDF placeholder later. | No /api/ledger. Client has score/changes (score_events) and portfolio score-history (score_change_log per property). | New endpoints under a path that enforces auth: **client** sees own ledger only; **admin** can pass client_id to see any client. Prefer **/api/client/ledger** and **/api/admin/ledger** (or single /api/ledger with scope by role) to avoid duplicate mounts. |
| **Frontend** | New page under Reports or Compliance: “Audit & Change History” with tabs **Score History** (ledger) and **Activity Log** (placeholder or reuse audit). Score History: filters (date, property, trigger type, actor), table (Timestamp \| Change \| Property \| Requirement \| Before→After \| Δ \| Actor \| View), row click → drawer (full details, driver breakdown, rule version, links). Export CSV button (same filters). | **ClientAuditLogPage** = general audit timeline; no Score History tab. **ReportsPage** = report generation. No ledger table, no drawer, no CSV export for score changes. “What Changed” on dashboard uses score_events, not a ledger. | New page or extend Reports: add “Audit & Change History” with Score History (ledger) + Activity Log (reuse GET portfolio/audit-timeline or admin-style audit). Add Export CSV. |
| **RBAC** | Client only own data; admin can access any client; audit log export actions. | Client routes use client_route_guard (own client_id). Admin uses admin_route_guard. | Enforce same pattern: client ledger filtered by request user’s client_id; admin ledger allows client_id query param and audit-log export. |
| **Trigger type enum** | DOCUMENT_UPLOADED, DOCUMENT_REMOVED, CERT_DETAILS_CONFIRMED, EXPIRY_DATE_EDITED, REQUIREMENT_NA_SET, PROPERTY_ADDED, PROPERTY_REMOVED, RULES_UPDATED, SCHEDULED_RECALC. | DOC_UPLOADED, DOC_DELETED, DOC_STATUS_CHANGED, AI_APPLIED, ADMIN_UPLOAD, ADMIN_DELETE, EXPIRY_JOB, PROVISIONING, PROPERTY_CREATED, PROPERTY_UPDATED, LAZY_BACKFILL. | **Naming overlap but not 1:1.** Task has CERT_DETAILS_CONFIRMED / EXPIRY_DATE_EDITED / REQUIREMENT_NA_SET / PROPERTY_REMOVED / RULES_UPDATED / SCHEDULED_RECALC. Map existing reasons to task trigger_type + trigger_label (e.g. DOC_STATUS_CHANGED → “Document status updated”, EXPIRY_JOB → “Scheduled recalc” or “Expiry rollover”). Do **not** rename existing queue reasons; add a mapping layer for ledger display. |
| **Entity refs** | property_id, requirement_id, document_id on each ledger entry. | Queue job has only property_id (and client_id). requirement_id/document_id are not in the queue; they exist at enqueue time in routes but are not passed through. | To populate requirement_id/document_id on the ledger, either (1) extend queue payload with optional `requirement_id`, `document_id` and pass them through to recalculate_and_persist → ledger, or (2) leave them null for async recalc and accept “Property X, trigger Y” only. Option (1) is more accurate but requires changing enqueue calls and queue schema. |
| **Driver breakdown** | drivers_before, drivers_after, drivers_delta: status, timeline, documents, overdue_penalty. | Breakdown in code: status_score, expiry_score, document_score, overdue_penalty_score, risk_score. | Map existing keys to task names (e.g. status_score→status, expiry_score→timeline, document_score→documents, overdue_penalty_score→overdue_penalty); risk_score can be extra or folded. |
| **Export** | CSV now; PDF later (placeholder). Audit log for export actions. | No score-ledger CSV. Admin has audit-log CSV in reporting_service. | Add streaming CSV for ledger with same filters as GET ledger; audit-log export when user downloads CSV. |

---

## 3. Conflicts and recommended resolution

### 3.1 New collection vs reusing score_change_log

- **Conflict:** Task asks for **score_ledger_events** with more fields (drivers, grades, rule_version, trigger_label, refs). **score_change_log** is property-scoped and minimal.  
- **Recommendation:** Add **score_ledger_events** as the new ledger. Keep **score_change_log** and **property_compliance_score_history** as-is for existing consumers (portfolio score-history, reports). Do **not** remove or replace them; the ledger is an additional, enterprise-grade log. Optionally, in the long term, deprecate reading score_change_log for “history” in favour of the ledger once the ledger is the source of truth for UI.

### 3.2 Single write point and double-logging

- **Recommendation:** Implement **log_score_change(...)** and call it **only from recalculate_and_persist** (with before/after scores and breakdowns already computed). That way every score-affecting action that goes through the queue produces exactly one ledger entry when the worker runs. Do **not** also write from routes (would duplicate when recalc runs). Idempotency: include `correlation_id` (and optionally a hash of correlation_id + property_id + created_at date) in the ledger document; before insert, check for existing entry with same idempotency key to avoid duplicates on worker retry.

### 3.3 Trigger type and label

- **Recommendation:** Keep internal **trigger_reason** values (TRIGGER_DOC_UPLOADED, etc.) in the queue and in recalculate_and_persist. In the ledger, store:
  - **trigger_type:** map to task-style enum (e.g. DOCUMENT_UPLOADED, DOCUMENT_REMOVED, SCHEDULED_RECALC for EXPIRY_JOB/LAZY_BACKFILL) for API/UI consistency.
  - **trigger_label:** human-readable string (e.g. from a small map trigger_reason → label).
So one source of truth (reason in queue), two display fields in the ledger.

### 3.4 requirement_id / document_id on ledger

- **Recommendation:** Phase 1: write ledger from recalculate_and_persist with **property_id** and **trigger_type**/trigger_label; leave **requirement_id** and **document_id** null for async recalc (worker does not have them unless we extend the queue). Phase 2 (optional): extend **compliance_recalc_queue** payload and worker to accept optional `requirement_id`, `document_id` from enqueue calls and pass them in context so the ledger can store them.

### 3.5 API path and RBAC

- **Recommendation:** Add **GET /api/client/ledger** (client_route_guard; filter by own client_id, optional property_id, trigger_type, from, to, limit, cursor) and **GET /api/client/ledger/export.csv** (same query params; stream CSV; audit-log the export). Add **GET /api/admin/ledger** (admin_route_guard; required or optional client_id to scope, same filters) and **GET /api/admin/ledger/export.csv** for admin export with audit. This keeps client vs admin clear and reuses existing auth.

### 3.6 “Activity Log” tab

- **Recommendation:** Reuse **GET /api/portfolio/audit-timeline** (or a thin wrapper) for the “Activity Log” tab so it shows login, document, email, etc. The “Score History” tab is ledger-only. No need for a second audit store.

### 3.7 PDF export

- **Recommendation:** Add a placeholder endpoint (e.g. GET /api/client/ledger/export.pdf) that returns 501 or a short “Coming soon” response. Implement PDF in a later iteration.

---

## 4. Implementation checklist (high level)

- **Backend**
  - [ ] Add **score_ledger_events** collection and indexes (client_id + created_at; client_id + property_id + created_at; client_id + trigger_type + created_at).
  - [ ] Add **log_score_change(...)** helper (inputs: client_id, property_id, requirement_id, document_id, actor_type, actor_id, trigger_type, trigger_label, before_score, after_score, before_grade, after_grade, drivers_before, drivers_after, rule_version, evidence, correlation_id for idempotency). Compute delta and drivers_delta; insert one document.
  - [ ] Call **log_score_change** from **recalculate_and_persist** (after updating property and writing score_change_log/history/audit). Map reason → trigger_type + trigger_label; pass breakdowns as drivers; set rule_version from result.
  - [ ] Add **GET /api/client/ledger** and **GET /api/client/ledger/export.csv** (client-scoped, with filters). Add **GET /api/admin/ledger** and **GET /api/admin/ledger/export.csv** (admin, optional client_id). Audit-log export actions.
  - [ ] (Optional) Extend queue payload and worker to pass requirement_id/document_id into context and into log_score_change.
- **Frontend**
  - [ ] Add page “Audit & Change History” (e.g. under Reports or new nav item): tabs **Score History** (ledger) and **Activity Log** (audit timeline).
  - [ ] Score History: filter bar (date range, property, trigger type, actor); table (Timestamp, Change, Property, Requirement, Before→After, Δ, Actor, View); row click → side drawer with full details, driver breakdown, rule version, links to document/requirement if present.
  - [ ] “Export CSV” button using current filters; call export.csv and trigger download.
  - [ ] Empty state and styling consistent with dashboard; timestamps in user local time (store UTC).
- **Command Centre / Dashboard**
  - [ ] Add “View what changed” link that opens last 20 ledger entries (e.g. new page or modal with ledger list).

---

## 5. Files to touch (reference)

| Area | Files |
|------|--------|
| Ledger collection + indexes | `backend/database.py` |
| Ledger write + recalc hook | `backend/services/compliance_scoring_service.py` (recalculate_and_persist); new module e.g. `backend/services/score_ledger_service.py` for log_score_change and trigger mapping |
| Client ledger API | New or extend `backend/routes/client.py` or `backend/routes/portfolio.py` |
| Admin ledger API | `backend/routes/admin.py` |
| Queue payload (optional refs) | `backend/services/compliance_recalc_queue.py`; all call sites of enqueue_compliance_recalc; `backend/job_runner.py` (worker context) |
| Frontend page + tabs | New page e.g. `frontend/src/pages/AuditChangeHistoryPage.js`; nav in `ClientPortalLayout` or Reports |
| Dashboard “View what changed” | `frontend/src/pages/ClientDashboard.js` or shared component |

---

## 6. Sample ledger entry (target shape)

After implementation, a single recalc could produce an entry like:

```json
{
  "client_id": "CLI-xxx",
  "property_id": "PROP-yyy",
  "requirement_id": null,
  "document_id": null,
  "actor_type": "user",
  "actor_id": "usr-zzz",
  "trigger_type": "DOCUMENT_UPLOADED",
  "trigger_label": "Document uploaded",
  "before_score": 72,
  "after_score": 78,
  "delta": 6,
  "before_grade": "C",
  "after_grade": "C",
  "drivers_before": { "status": 70, "timeline": 75, "documents": 68, "overdue_penalty": 80 },
  "drivers_after": { "status": 72, "timeline": 76, "documents": 82, "overdue_penalty": 80 },
  "drivers_delta": { "status": 2, "timeline": 1, "documents": 14, "overdue_penalty": 0 },
  "rule_version": "v1",
  "evidence": {},
  "created_at": "2026-03-01T12:00:00.000Z",
  "correlation_id": "DOC_UPLOADED:PROP-yyy:173..."
}
```

This audit is the single reference for implementing the Score Ledger and Audit Trail without duplicating or conflicting with **score_change_log**, **score_events**, or **property_compliance_score_history**. Implement step by step; do not implement blindly.
