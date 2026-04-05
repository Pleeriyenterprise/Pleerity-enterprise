# Client portal — button / endpoint workflow matrix

This document maps **explicit UI actions** to **HTTP endpoints** and **intended outcomes** for requirements, compliance jobs, maintenance jobs, and Today inbox items. It reflects the implemented API under `/api` unless a row notes a product-only nuance.

## General rules

- Each control has **one purpose**; inbox visibility actions do not change compliance truth.
- **Creating a job** is not a booking; **booking** is not completion; **completion** is not compliance until proof and (for compliance) **verify** are satisfied.
- **Mark not applicable** retains the requirement for audit/reporting (no deletion).

## Scheduling field names (implementation)

- Booking uses **`scheduled_at`** (ISO datetime) and **`timezone`** (IANA) on `POST .../request-booking` and `.../reschedule`, not separate `scheduled_start` / `scheduled_end` fields.

---

## Requirement card actions

| Button / action | Endpoint | Outcome / notes |
|-----------------|----------|-----------------|
| Upload certificate | **Direct API:** `POST /api/requirements/{requirement_id}/documents` (`routes/api_compliance_workflow.py`). **Multipart form:** required `file` (`UploadFile`); optional form fields `document_type`, `notes`, `work_order_id` (validated against client/property/requirement when present). Auth: client session (`_require_client`); rate limit: same as vault upload. **Response JSON:** `{ "message", "document_id", "outcome" }` — `outcome` is the compliance outcome-engine result for `EVENT_CERTIFICATE_UPLOADED`, or omitted/null if that step skips. **Server-side:** persists `documents` row (`UPLOADED`), optional async analysis, property compliance refresh, compliance recalc enqueue (`TRIGGER_DOC_UPLOADED`), score/audit/analytics hooks. **Does not by itself** set requirement `COMPLIANT` / `VALID`; that follows verification / admin document verify and linking flows. **UI today:** requirement cards and Today often **navigate** to `/documents?property_id=…&requirement_id=…&focus=upload` and use the shared vault upload path; the requirement-scoped POST is the canonical programmatic equivalent when uploading against a specific requirement. |
| Create compliance work order | `POST /api/requirements/{requirement_id}/jobs` | Creates **COMPLIANCE** work order; client should navigate to `/operations/jobs/{job_id}`. Requirement moves toward in-progress with active job linkage (see service rules). |
| Mark as not applicable | `POST /api/requirements/{requirement_id}/mark-not-applicable` (reason required) | Requirement **NOT_APPLICABLE**; retained for reporting; may close linked active compliance job per policy. |
| View requirement | Navigate `/requirements/{requirement_id}`; detail `GET /api/requirements/{requirement_id}` | Read-only navigation. |

**UX:** No top-level **“Arrange inspection”** on requirement cards; booking lives on the **job** workflow only.

---

## Compliance job actions

**Page sections (UI):** Summary · Assignment · Scheduling · Execution · **Evidence** · Timeline.

| # | Action | Endpoint | Notes |
|---|--------|----------|-------|
| 1 | Assign contractor | `POST /api/jobs/{job_id}/assign-contractor` | Requires contractor before **request-booking** (API enforces). |
| 2 | Request booking | `POST /api/jobs/{job_id}/request-booking` | Body: `scheduled_at`, `timezone`, optional `notes`. |
| 3 | Confirm appointment | `POST /api/jobs/{job_id}/confirm-booking` | Requires a proposed `scheduled_at` / schedule row. |
| 4 | Reschedule | `POST /api/jobs/{job_id}/reschedule` | Same behaviour as request-booking; preserves job history; clears/replaces schedule per schedule service. |
| 5a | Mark no access | `POST /api/jobs/{job_id}/mark-no-access` | Sets operational exception → canonical **NO_ACCESS**. |
| 5b | Mark reschedule required | `POST /api/jobs/{job_id}/mark-reschedule-required` | Sets **RESCHEDULE_REQUIRED** (same family as no-access; clear via `operational-exception` or recovery actions). |
| 6 | Mark visit in progress | `POST /api/jobs/{job_id}/start` | **BOOKED** → **IN_PROGRESS** (subject to server rules). |
| 7 | Mark work complete | `POST /api/jobs/{job_id}/complete` | **IN_PROGRESS** → **COMPLETED**. |
| 8 | Attach compliance certificate | `POST /api/jobs/{job_id}/link-document` `{ document_id }` | Adds vault document to job evidence. |
| 9 | Verify and close (compliance) | `POST /api/jobs/{job_id}/verify` | **COMPLETED** → **VERIFIED**; **requires linked proof** on the job or API returns 400. Requirement **COMPLIANT** / **VALID** is driven by **document verification / admin flows** (see document verify tests), not solely by this POST. |
| 10 | Cancel work order | `POST /api/jobs/{job_id}/cancel` | Job cancelled; history preserved. |
| — | Cancel booking only | `POST /api/jobs/{job_id}/cancel-booking` | Clears schedule fields; **does not** cancel the job. |
| — | Set / clear operational hold | `POST /api/jobs/{job_id}/operational-exception` | Alternative to dedicated mark-* endpoints for **NO_ACCESS**, **RESCHEDULE_REQUIRED**, **FOLLOW_UP_REQUIRED**, or clear. |

**Canonical states exposed in UI include:** **NO_ACCESS**, **RESCHEDULE_REQUIRED**, **FOLLOW_UP_REQUIRED** (operational holds), plus normal booking/execution states.

**Disallowed:** booking without contractor; verify without linked proof.

---

## Maintenance job actions

**Page sections (UI):** Summary · Assignment · Scheduling · Execution · **Completion proof** · Timeline.

| # | Action | Endpoint | Notes |
|---|--------|----------|-------|
| 1 | Assign contractor | `POST /api/jobs/{job_id}/assign-contractor` | Same as compliance. |
| 2 | Request booking | `POST /api/jobs/{job_id}/request-booking` | Same body as compliance. |
| 3 | Confirm appointment | `POST /api/jobs/{job_id}/confirm-booking` | |
| 4 | Reschedule | `POST /api/jobs/{job_id}/reschedule` | |
| 5 | Mark visit in progress | `POST /api/jobs/{job_id}/start` | |
| 6 | Mark awaiting parts | `POST /api/jobs/{job_id}/awaiting-parts` | **MAINTENANCE only**; **IN_PROGRESS** → **AWAITING_PARTS**. |
| 7 | Resume after parts | `POST /api/jobs/{job_id}/resume-after-parts` | **AWAITING_PARTS** → **IN_PROGRESS**. |
| 8 | Mark work complete | `POST /api/jobs/{job_id}/complete` | **IN_PROGRESS** or **AWAITING_PARTS** → **COMPLETED** (policy-aligned with contractor status matrix). |
| 9 | Attach completion proof | `POST /api/jobs/{job_id}/attach-completion-proof` `{ document_id }` | Maintenance-specific. |
| 10 | Close job | `POST /api/jobs/{job_id}/close` | **COMPLETED** + proof → **VERIFIED**; **VERIFIED** → **CLOSED**; linked issue **RESOLVED** when policy applies. **`POST .../verify` is rejected for maintenance** — use attach proof + **close** only. |
| 11 | Cancel work order | `POST /api/jobs/{job_id}/cancel` | |
| — | Mark no access / reschedule / follow-up | `mark-no-access`, `mark-reschedule-required`, or `operational-exception` | Same holds as compliance where applicable. |

**States:** **AWAITING_PARTS**; **FOLLOW_UP_REQUIRED** via operational exception when needed.

---

## Today page

### Business actions (may route to workflows above)

- Upload certificate, create compliance work order, create maintenance job, review risk signal, view requirement, view issue — each navigates or calls the relevant **requirement/job/issue** API; they do **not** substitute for verify or booking rules on the job.

### Visibility / inbox only (do not change compliance outcome)

- Snooze 1 / 7 days: `POST /api/today/items/{item_id}/snooze` body `{ "days": <int 1–30> }` (UI uses 1 or 7).
- Mark reviewed: `POST /api/today/items/{item_id}/mark-reviewed` (empty body).
- Dismiss: `POST /api/today/items/{item_id}/dismiss` body `{ "reason": "<string, min length 3>" }`.

### Restore (inbox presentation only)

- `POST /api/today/items/{item_id}/restore` (empty body) — clears the client task override via `apply_task_action(..., restore)` so the item can show again in active sections. Shown on **hidden** bucket rows in the Today payload (`visibility_actions`: restore only). Does not change requirement/job/document truth.

---

## Job contractor creation & assignment (governance)

**Canonical flow:** `POST /api/contractors` (optional `work_order_id` for compliance capability stamping) then `POST /api/jobs/{job_id}/assign-contractor`.

**Creation (`contractor_service.create_contractor_for_client_job_portal`):**

| Portal role | Contact | Record type | Lifecycle / governance |
|-------------|---------|-------------|-------------------------|
| `ROLE_CLIENT` | Email present | `client_supplied_personal` | `pending_admin_review` → status **pending_approval**; **email dedupe** (same normalised email returns existing row for that client); name collision rules for personal contractors. |
| `ROLE_CLIENT` | Phone only | `landlord_added` | **pending_approval** + vetting note; **no** email dedupe path (global email uniqueness still applies if email added later). |
| Other roles (e.g. client admin) | Email | `landlord_added` | **Approved** directory row for the org (not pending). |
| Other roles | Phone only | `landlord_added` | **Approved**. |

Optional fields (region, areas served, credentials, accreditation, notes) are stored on the contractor document. Compliance jobs: `execution_capabilities` / `supported_requirement_codes` are derived from the linked work order when `work_order_id` is supplied.

**Assignment (`assign-contractor`):** `contractor_service.validate_contractor_for_work_order_assignment` chooses profile from the **contractor `source_type`**:

- `client_supplied_personal` → relaxed portal path (no vetted/portal-activated gate).
- `landlord_added` **and** `client_id` matches → `client_portal_landlord_contractor` (unvetted org directory rows: still enforce visibility, property scope, execution capability, location, trade).
- Otherwise → **strict** `compliance` / `standard` (vetted, portal activated, etc.) for network / shared contractors.

**Legacy:** `POST /api/jobs/{job_id}/create-personal-contractor-and-assign` is **deprecated** in OpenAPI; it delegates to the same `create_contractor_for_client_job_portal` + assignment resolver so it cannot drift from the two-step flow.

---

## Traceability

- `services/compliance_workflow_service.py` — `derive_canonical_job_status`, `next_actions`, `serialize_client_job`.
- `routes/api_compliance_workflow.py` — job lifecycle routes.
- `services/contractor_service.py` — `create_contractor_for_client_job_portal`, `ASSIGNMENT_PROFILE_CLIENT_PORTAL_LANDLORD`, assignment validation.
- Tests: `test_compliance_workflow_maintenance_canonical.py`, `test_compliance_job_next_actions_compliance_kind.py`, `test_job_awaiting_parts_and_reschedule_http.py`, `test_job_verify_policy_http.py`, `test_workflow_contractors_http.py`, schedule lifecycle tests.
